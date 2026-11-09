import json
import time
import unittest
from unittest.mock import patch
import numpy as np
from chery_showroom.controller import Showroom
from chery_showroom.localization import message,localize,message_key,CATALOG


class BilingualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=Showroom()
    @classmethod
    def tearDownClass(cls):cls.app.close()
    def setUp(self):self.app.reset();self.app.commands.queue.clear()
    def tick(self):self.app.last_client=time.monotonic();self.app.tick()
    def command(self,action,**values):
        self.app.command(dict(action=action,run_id=self.app.run_id,**values));self.tick()
    def until(self,predicate,limit=30):
        end=self.app.sim.data.time+limit
        while not predicate():
            self.tick()
            if self.app.sim.data.time>end:self.fail(str(self.app.state))
    def begin(self):
        self.until(self.app.ready_for_visit)
        self.command('start_visit');self.until(lambda:self.app.interactive.stage=='choose')
    def test_language_templates_and_reception(self):
        from chery_showroom.reception import ReceptionDesk
        for key,variants in CATALOG['messages'].items():
            values=dict(car='BMW X1',year=2013)
            self.assertEqual(localize(message(key,**values),'cs'),message(key,'cs',**values),key)
            self.assertEqual(message_key(message(key,**values)),key)
        desk=ReceptionDesk()
        reply=desk.respond(dict(text='Kolik stojí auto?',car='tiggo8',run_id='a'),'a','cs')
        self.assertIn('ověřen',reply['reply'])
        self.assertEqual(desk.respond(dict(text='How much does this car cost?',car='tiggo8',run_id='a'),'a','en')['language'],'en')
    def test_start_selection_consent_and_stale_generation(self):
        self.command('set_language',language='cs');self.until(self.app.ready_for_visit)
        old=self.app.run_id;before=self.app.sim.data.qpos[:2].copy()
        self.command('start_visit');self.assertNotEqual(old,self.app.run_id)
        self.assertLess(np.linalg.norm(before-self.app.sim.data.qpos[:2]),.02)
        with self.assertRaises(ValueError):self.app.command(dict(action='chat',text='ano',run_id=old))
        self.until(lambda:self.app.interactive.stage=='choose')
        self.command('select',car='tiggo7');self.assertFalse(self.app.path)
        self.assertIn('Volvo',self.app.state['message']);self.assertIn('Přejete',self.app.state['message'])
        self.command('set_language',language='en');self.assertEqual(self.app.language,'cs')
        self.command('chat',text='ano');self.assertTrue(self.app.path)
        self.command('stop');self.assertEqual(self.app.interactive.stage,'paused');self.assertFalse(self.app.path)
        self.assertFalse(self.app.gesture_until)
        for _ in range(10):self.tick()
        self.assertEqual(self.app.interactive.stage,'paused')
        self.command('reset');self.assertEqual(self.app.language,'cs')
        self.assertFalse(any(self.app.visit.needs.values()));self.assertFalse(self.app.visit.topics)
    def test_disconnect_does_not_resume_and_continue_recovers(self):
        self.begin();self.command('select',car='tiggo8');self.command('chat',text='yes')
        self.app.last_client=time.monotonic()-3;self.app.tick()
        self.assertEqual(self.app.failure_code,'disconnected');self.assertEqual(self.app.interactive.stage,'paused')
        self.tick();self.assertFalse(self.app.path)
        self.command('interactive_continue');self.assertEqual(self.app.interactive.stage,'escort')
    def test_blocked_route_and_timeout_require_correct_recovery(self):
        self.begin();self.command('select',car='tiggo4')
        with patch.object(self.app.navigator,'route',side_effect=ValueError('blocked')):
            self.command('chat',text='yes')
        self.assertEqual(self.app.failure_code,'blocked');self.assertFalse(self.app.path)
        self.command('interactive_continue');self.assertEqual(self.app.interactive.stage,'escort')
        with patch.object(self.app.sim,'_request_policy',side_effect=TimeoutError('test timeout')):self.tick()
        self.assertEqual(self.app.failure_code,'policy_timeout');self.assertFalse(self.app.path)
        self.command('interactive_continue');self.assertEqual(self.app.interactive.stage,'paused')
        self.command('reset');self.assertFalse(self.app.error);self.assertFalse(self.app._policy_failed)
    def test_audit_excludes_transcripts_and_preferences(self):
        self.begin();self.app.visit.needs['budget']='PRIVATE CUSTOMER';self.app.visit.topic('PRIVATE TRANSCRIPT')
        self.command('reset')
        raw=json.dumps(self.app.visit_reports[-1]);self.assertNotIn('PRIVATE',raw)
        self.assertIn('physics_ms',raw);self.assertEqual(self.app.visit_reports[-1]['status'],'reset')
    def test_return_uses_wide_aisle_and_reception_approach(self):
        self.begin();self.app.selected=self.app.interactive.car='tiggo8'
        self.app.sim.data.qpos[:2]=self.app.sim.model.site('vehicle_3').pos[:2]
        self.app.sim.forward();before=self.app.sim.data.qpos[:2].copy()
        self.app.interactive.stage='returning';self.app.interactive.actor_state='stopped'
        self.app.commands.put(('interactive_return','tiggo8',self.app.run_id));self.tick()
        self.assertFalse(self.app.error);self.assertEqual(self.app.return_leg,'entry')
        self.assertAlmostEqual(self.app.path[-1][1],.75)
        self.assertTrue(self.app.return_navigator.free(self.app.sim.model.site('reception_approach').pos[:2]))
        self.assertGreater(self.app.return_navigator.clearance,self.app.navigator.clearance)
        self.assertLess(np.linalg.norm(self.app.sim.data.qpos[:2]-before),.02)
    def test_reception_uses_current_preferences_without_owning_movement(self):
        from chery_showroom.reception import ReceptionDesk
        context={'needs':{'use':'family','passengers':'4','priority':'space','budget':None},'topics':['car comparison']}
        reply=ReceptionDesk().respond(dict(text='summary',car='tiggo7',run_id='a'),'a','cs',context)
        self.assertIn('family',reply['reply']);self.assertIn('Počet cestujících: 4',reply['reply'])
        self.assertEqual(context['topics'],['car comparison'])
    def test_waypoint_tolerance_does_not_cut_chair_corner(self):
        self.begin();self.app.sim.data.qpos[:2]=[-1.943,-.017]
        self.app.sim.data.qpos[3:7]=[0.,0.,0.,1.];self.app.sim.forward()
        self.app.interactive.stage='returning';self.app.interactive.actor_state='stopped'
        self.app.destination='reception';self.app.phase='escort'
        self.app.path=[(-2.05,0.),(-2.2,-1.48)]
        self.assertTrue(self.app.navigator.free(self.app.sim.data.qpos[:2]))
        self.assertFalse(self.app.navigator.segment_free(self.app.sim.data.qpos[:2],self.app.path[1]))
        self.tick()
        self.assertFalse(self.app.error);self.assertEqual(self.app.path[0],(-2.05,0.))
    def test_ending_before_consent_keeps_robot_at_reception(self):
        self.begin();before=self.app.sim.data.qpos[:2].copy()
        self.command('end_visit')
        self.until(lambda:self.app.interactive.stage=='completed' and self.app.ready_for_visit(),30)
        self.assertEqual(self.app.return_leg,'home')
        self.assertLess(np.linalg.norm(self.app.sim.data.qpos[:2]-before),.18)


if __name__=='__main__':unittest.main()
