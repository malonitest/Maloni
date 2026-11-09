"""Real-policy interactive visit acceptance and cancellation boundaries."""
import json
import time
import unittest
from pathlib import Path
import numpy as np
from chery_showroom.runtime import Showroom
from chery_showroom.arrival_export import checked_tick


class InteractiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Showroom()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def setUp(self):
        self.app.reset()
        self.app.commands.queue.clear()

    def command(self, action, text=''):
        self.app.command(dict(action=action, text=text))
        checked_tick(self.app)

    def until(self, predicate, seconds=65):
        deadline = self.app.sim.data.time+seconds
        while not predicate():
            checked_tick(self.app)
            if self.app.sim.data.time > deadline:
                self.fail(str(self.app.interactive.snapshot())+' '+self.app.message)

    def offer(self):
        self.command('interactive_start')
        self.until(lambda: self.app.interactive.stage == 'offer')

    def presentation(self):
        self.offer()
        self.command('chat', 'yes')
        self.until(lambda: self.app.interactive.stage == 'presentation')

    def test_three_complete_runs(self):
        reports=[]
        for _ in range(3):
            self.presentation()
            v=self.app.interactive
            self.assertFalse(self.app.demo.active)
            self.assertIsNotNone(v.arrived_at)
            self.assertGreaterEqual(v.min_separation, 1.2)
            self.assertTrue(self.app.facing_vehicle('tiggo8'))
            self.assertEqual(sum(e['event']=='welcome' for e in v.events), 1)
            self.assertEqual(sum(e['event']=='arrived' for e in v.events), 1)
            for part in range(3):
                self.assertEqual(v.part, part)
                self.command('chat', 'How much does it cost and what equipment does it have?')
                self.assertIn('do not have a verif', self.app.message)
                self.assertEqual(v.stage, 'questions')
                self.assertFalse(self.app.gesture_until)
                self.command('interactive_continue')
                self.until(lambda: v.stage=='presentation')
                self.assertEqual(v.part, part)  # interrupted section resumes
                if part<2:
                    self.command('interactive_continue')
                    self.until(lambda: v.part==part+1)
            self.command('handoff')
            self.assertEqual(v.stage, 'handoff')
            self.assertIn('no booking', self.app.message)
            reports.append(v.snapshot())
        # Acceptance artifact contains measured real-policy runs, no customer data.
        folder=Path('/tmp/maloni-interactive-review');folder.mkdir(exist_ok=True)
        (folder/'acceptance.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))

    def test_refusal_and_zone_reentry_do_not_regreet(self):
        self.offer()
        self.command('chat', 'možná')
        self.assertEqual(self.app.interactive.stage, 'offer')
        self.assertFalse(self.app.path)
        self.command('chat', 'Yes?')
        self.assertEqual(self.app.interactive.stage, 'offer')
        self.assertFalse(self.app.path)
        self.command('chat', 'ne')
        self.command('customer', 'approach')
        for _ in range(30):checked_tick(self.app)
        self.assertEqual(self.app.interactive.stage, 'declined')
        self.assertEqual(sum(e['event']=='welcome' for e in self.app.interactive.events), 1)
        self.command('chat', 'ano')
        self.assertFalse(self.app.path)

    def test_customer_stops_robot_waits_requires_explicit_resume(self):
        self.offer()
        self.command('chat', 'ano')
        self.command('customer', 'stop')
        self.until(lambda: self.app.interactive.stage=='paused')
        self.assertIn('fallen behind', self.app.interactive.reason)
        self.assertFalse(self.app.path)
        self.command('interactive_continue')
        self.assertEqual(self.app.interactive.stage, 'paused')
        self.command('customer', 'approach')
        self.until(lambda: np.linalg.norm(self.app.interactive.actor.position-self.app.sim.data.qpos[:2])<1.95)
        self.assertEqual(self.app.interactive.stage, 'paused')
        self.command('interactive_continue')
        self.until(lambda: self.app.interactive.stage=='presentation')

    def test_dynamic_guard_and_no_false_presentation(self):
        self.offer()
        v=self.app.interactive
        # Deliberate injected test obstacle, not a customer movement API.
        v.actor.pose(self.app.sim.data.qpos[:2]+[1.3,0],0,False)
        self.assertTrue(np.all(v.guard(np.array([.22,0,0]))==0))
        self.assertEqual(v.stage,'paused')
        self.assertFalse(self.app.path)
        self.command('interactive_continue')
        self.assertEqual(v.stage,'paused')
        v.stage='questions'
        v.present()
        self.assertFalse(self.app.gesture_until)
        self.assertNotEqual(v.stage,'presentation')

    def test_stop_and_reset_in_main_phases(self):
        for phase in ('arrival','escort','presentation'):
            if phase=='presentation':self.presentation()
            elif phase=='escort':
                self.offer();self.command('chat','ano')
            else:self.command('interactive_start')
            self.command('stop')
            position=self.app.interactive.actor.position.copy()
            self.assertEqual(self.app.interactive.stage,'paused')
            for _ in range(20):checked_tick(self.app)
            np.testing.assert_allclose(self.app.interactive.actor.position,position)
            self.assertFalse(self.app.gesture_until)
            self.assertFalse(self.app.path)
            self.app.visit.needs['budget']='private'
            self.command('reset')
            self.assertFalse(self.app.interactive.active)
            self.assertNotIn('private',str(self.app.visit.snapshot()))
            self.assertLess(self.app.sim.data.mocap_pos[0,2],-5)

    def test_stale_commands_and_repeated_start_are_isolated(self):
        self.offer()
        old=self.app.run_id
        self.app.command(dict(action='reset'))
        self.app.command(dict(action='chat',text='ano',run_id=old))
        checked_tick(self.app)
        self.assertFalse(self.app.path)
        with self.assertRaises(ValueError):
            self.app.command(dict(action='interactive_start',run_id=old))
        self.command('interactive_start')
        self.app.commands.put(('interactive_escort','tiggo8',old))
        checked_tick(self.app)
        self.assertFalse(self.app.path)
        self.command('scenario')
        self.assertTrue(self.app.demo.active)
        self.assertFalse(self.app.interactive.active)

    def test_panel_loss_pauses_customer_and_movement(self):
        self.offer();self.command('chat','yes')
        self.app.last_client=time.monotonic()-3
        self.app.tick()
        self.assertEqual(self.app.interactive.stage,'paused')
        self.assertFalse(self.app.path)
        self.assertFalse(self.app.gesture_until)
        self.assertEqual(self.app.interactive.actor_state,'stopped')
        self.assertIn('connection lost',self.app.message)
        # A restored heartbeat still requires the customer to return to safe range.
        self.app.command(dict(action='customer',text='approach'))
        for _ in range(400):
            self.app.last_client=time.monotonic();self.app.tick()
            distance=np.linalg.norm(self.app.interactive.actor.position-self.app.sim.data.qpos[:2])
            if 1.45 <= distance < 1.95:break
        self.assertTrue(1.45 <= distance < 1.95)
        self.command('interactive_continue')
        self.assertNotEqual(self.app.interactive.stage,'paused')
        self.assertFalse(self.app.error)

    def test_limited_targets_and_consent_gate(self):
        self.command('interactive_start')
        for target in ('teleport','vehicle_1','1,2'):
            with self.assertRaises(ValueError):self.app.command(dict(action='customer',text=target))
        self.command('chat','ano')
        self.assertFalse(self.app.path)
        self.command('escort')
        self.assertFalse(self.app.path)

    def test_exit_uses_route_and_finishes_without_second_greeting(self):
        self.presentation()
        old=self.app.interactive.actor.position.copy()
        self.command('customer','exit')
        self.assertLess(np.linalg.norm(self.app.interactive.actor.position-old),.03)
        self.until(lambda:self.app.interactive.stage=='completed')
        self.assertFalse(self.app.path)
        self.assertEqual(sum(e['event']=='welcome' for e in self.app.interactive.events),1)

    def test_other_car_question_keeps_actual_selected_car(self):
        self.presentation()
        self.command('chat','Chci vidět Volvo')
        self.assertEqual(self.app.selected,'tiggo8')
        self.assertEqual(self.app.visit.selected,'tiggo8')
        self.assertEqual(self.app.interactive.stage,'questions')
        self.assertFalse(self.app.path)

    def test_http_auth_actions_and_voice_cancellation_ownership(self):
        import re
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        from unittest.mock import patch
        from chery_showroom.runtime import server
        app=self.app
        checked_tick(app)
        with patch('chery_showroom.voice.ShowroomProvider') as provider:
            instance=provider.return_value
            instance.configured=False
            instance.create.side_effect=[
                {'session':{'id':'voice-old'},'transport':{'sdp':'fake-answer'}},
                {'session':{'id':'voice-new'},'transport':{'sdp':'fake-answer'}},
                {'session':{'id':'voice-stop'},'transport':{'sdp':'fake-answer'}},
            ]
            http=server(app)
            root=f'http://127.0.0.1:{http.server_port}'
            try:
                html=urlopen(root).read().decode()
                token=re.search("const token='([^']+)'",html)[1]
                def request(path,body=None,auth=True):
                    req=Request(root+path,data=None if body is None else json.dumps(body).encode(),
                                headers={'X-Showroom-Token':token if auth else '', 'Content-Type':'application/json'})
                    with urlopen(req) as r:return r.status,r.read()
                self.assertEqual(request('/interactive.js')[0],200)
                with self.assertRaises(HTTPError) as err:request('/action',dict(action='interactive_start'),False)
                self.assertEqual(err.exception.code,403)
                self.assertEqual(request('/action',dict(action='interactive_start',run_id=app.run_id))[0],202)
                checked_tick(app)
                state=json.loads(request('/state')[1])
                self.assertEqual(state['language'],'en')
                self.assertEqual(state['demo_audio_language'],'en')
                self.assertTrue(state['interactive']['active'])
                old=app.run_id
                request('/session',dict(sdp='fake',run_id=old))
                app.reset();checked_tick(app)
                request('/cancel',dict(session_id='voice-old'))
                self.assertTrue(app.commands.empty())  # stale hangup never stops a new visit
                request('/session',dict(sdp='fake',run_id=app.run_id))
                request('/cancel',dict(session_id='voice-new',interruption=True))
                self.assertTrue(app.commands.empty())  # intentional speech interruption preserves escort
                request('/session',dict(sdp='fake',run_id=app.run_id))
                request('/cancel',dict(session_id='voice-stop'))
                self.assertFalse(app.commands.empty())  # explicit voice disconnect stops locomotion
                checked_tick(app)
                with self.assertRaises(HTTPError) as err:request('/action',dict(action='chat',text='ano',run_id=old))
                self.assertEqual(err.exception.code,400)
            finally:
                http.close_sessions();http.shutdown();http.server_close()

    def test_pending_presentation_is_cancelled_by_stop_and_exit(self):
        self.presentation()
        v=self.app.interactive
        v.pending_part=False
        self.command('stop')
        self.assertIsNone(v.pending_part)
        for _ in range(10):checked_tick(self.app)
        self.assertEqual(v.stage,'paused')
        self.assertFalse(self.app.gesture_until)
        self.command('interactive_continue')
        self.until(lambda:v.stage=='presentation')
        v.pending_part=False
        self.command('customer','exit')
        self.assertIsNone(v.pending_part)
        self.assertEqual(v.stage,'leaving')
        self.assertFalse(self.app.gesture_until)

    def test_refusal_during_escort_stops_both_actors(self):
        self.offer();self.command('chat','ano')
        self.assertTrue(self.app.path)
        self.command('chat','Nechci pokračovat')
        self.assertEqual(self.app.interactive.stage,'declined')
        self.assertFalse(self.app.path)
        self.assertEqual(self.app.interactive.actor_state,'stopped')
        self.command('chat','ano')
        self.assertFalse(self.app.path)

    def test_reset_racing_command_validation_cannot_retag_old_input(self):
        app=self.app
        old=app.run_id
        class ResetDuringValidation(dict):
            def get(self,key,default=None):
                if key=='run_id':
                    app.reset()
                    return old
                return super().get(key,default)
        app.command(ResetDuringValidation(action='interactive_start',run_id=old))
        checked_tick(app)
        self.assertNotEqual(app.run_id,old)
        self.assertFalse(app.interactive.active)
