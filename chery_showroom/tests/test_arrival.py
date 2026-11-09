"""Arrival scenario acceptance, interruption and voice/export guards."""
import json
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
import mujoco
import numpy as np
from chery_showroom.runtime import Showroom
from chery_showroom.arrival import SCRIPT,DURATION,CUSTOMER_START
from chery_showroom.arrival_export import checked_tick,finish_check,export,subtitles
from chery_showroom.voice_assets import prepare,validate,mix,inspect_wav


class ArrivalPhysicsTests(unittest.TestCase):
    def setUp(self):self.app=Showroom()
    def tearDown(self):self.app.close()
    def advance(self,t):
        while self.app.demo.active and self.app.demo.elapsed<t:checked_tick(self.app)

    def test_three_complete_runs_with_one_trigger_and_safe_clearance(self):
        for _ in range(3):
            self.app.demo.start()
            while self.app.demo.active:checked_tick(self.app)
            report=finish_check(self.app)
            self.assertEqual(report['elapsed'],55)
            self.assertLessEqual(report['arrived_at'],34)
            self.assertGreaterEqual(report['min_separation'],1.2)
            self.assertEqual(sum(e['event']=='cue:welcome' for e in report['events']),1)

    def test_customer_is_visible_articulated_and_does_not_change_robot_dofs(self):
        app=self.app;app.demo.start();self.advance(8)
        m,d=app.sim.model,app.sim.data;actor=m.body('demo_customer').id
        self.assertEqual(m.nq,36);self.assertEqual(m.nv,35)
        self.assertEqual(m.body_mass[actor],0)
        ids=list(app.demo.actor.ids.values())
        self.assertFalse(np.any(m.geom_contype[ids]));self.assertFalse(np.any(m.geom_conaffinity[ids]))
        head=m.geom('customer_head').id
        self.assertAlmostEqual(d.geom_xpos[head,2]-d.mocap_pos[0,2],1.65,places=5)
        self.assertGreater(np.linalg.norm(app.demo.actor.position-CUSTOMER_START),3)
        self.assertTrue(app.gesture_until)  # reaction uses the existing bounded greeting gesture

    def test_stop_during_arrival_walk_and_presentation(self):
        app=self.app
        for at in (3,18,36):
            app.demo.start();self.advance(at)
            app.command(dict(action='stop'));checked_tick(app)
            pos=app.demo.actor.position.copy()
            self.assertFalse(app.demo.active);self.assertEqual(app.demo.status,'stopped')
            self.assertFalse(app.path);self.assertFalse(app.gesture_until);self.assertIsNone(app.demo.cue)
            for _ in range(20):checked_tick(app)
            np.testing.assert_allclose(app.demo.actor.position,pos)

    def test_render_wall_time_is_not_navigation_stall_time(self):
        app=self.app;app.demo.start();self.advance(12.2)
        self.assertTrue(app.path)
        simulated_progress=app.last_progress
        with patch('chery_showroom.runtime.time.monotonic',return_value=1000000.):
            app.last_client=1000000.;app.tick()
        self.assertFalse(app.error)
        self.assertTrue(app.demo.active)
        self.assertLess(app.sim.data.time-simulated_progress,1.)

    def test_restart_discards_previous_run_script_commands(self):
        app=self.app;app.demo.start();old=app.run_id
        app.commands.put(('scenario','tiggo8',''))
        app.commands.put(('demo_escort','tiggo8',old))
        checked_tick(app)
        self.assertNotEqual(app.run_id,old)
        self.assertTrue(app.demo.active)
        self.assertFalse(app.path)
        self.assertEqual(app.demo.status,'arrival')

    def test_reset_restores_both_actors_and_visit(self):
        app=self.app;original_shadows=app.sim.model.light_castshadow.copy();app.demo.start();self.advance(18)
        self.assertEqual(int(np.sum(app.sim.model.light_castshadow)),1)
        app.visit.needs['budget']='private'
        app.command(dict(action='reset'));checked_tick(app)
        self.assertEqual(app.demo.status,'idle')
        np.testing.assert_array_equal(app.sim.model.light_castshadow,original_shadows)
        self.assertLess(app.sim.data.mocap_pos[0,2],-5)
        np.testing.assert_allclose(app.demo.actor.position,CUSTOMER_START)
        self.assertNotIn('private',str(app.visit.snapshot()))
        app.demo.start();self.assertTrue(app.demo.active);self.assertFalse(app.demo.triggered)

    def test_blocked_route_and_deadline_never_start_presentation(self):
        app=self.app;app.demo.start();self.advance(11.9)
        with patch.object(app.navigator,'route',side_effect=ValueError('blocked')):
            while not app.error:app.last_client=time.monotonic();app.tick()
        self.assertEqual(app.demo.status,'failed');self.assertFalse(app.demo.presentation_started)
        self.assertFalse(app.gesture_until)
        app.demo.start();self.advance(11)
        app.demo.travel_started=True;app.demo.started=app.sim.data.time-34.1
        app.demo.update()
        self.assertEqual(app.demo.status,'failed')
        self.assertIn('in time',app.message)
        self.assertFalse(app.demo.presentation_started)

    def test_stale_panel_and_manual_override_stop_script(self):
        app=self.app;app.demo.start();self.advance(1)
        app.last_client=time.monotonic()-3;app.tick()
        self.assertFalse(app.demo.active);self.assertEqual(app.demo.status,'failed')
        app.demo.start();self.advance(18)
        app.command(dict(action='escort',car='tiggo7'));checked_tick(app)
        self.assertEqual(app.demo.status,'stopped')
        self.assertEqual(app.selected,'tiggo7')


class ArrivalAudioTests(unittest.TestCase):
    def tone(self,path,seconds=.15,silent=False):
        samples=(np.zeros(round(seconds*24000)) if silent else
                 3000*np.sin(np.arange(round(seconds*24000))*2*np.pi*400/24000)).astype('<i2')
        with wave.open(str(path),'wb') as f:
            f.setparams((1,2,24000,0,'NONE','not compressed'));f.writeframes(samples.tobytes())

    def test_import_validate_mix_and_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();cache=root/'cache'
            for cue in SCRIPT['cues']:self.tone(source/(cue['id']+'.wav'))
            manifest=prepare(cache,source_dir=source)
            self.assertFalse(manifest['ai_generated'])
            self.assertEqual(manifest['language'],'en')
            self.tone(source/'welcome.wav',seconds=.25)
            manifest=prepare(cache,source_dir=source)
            self.assertAlmostEqual(manifest['cues']['welcome']['duration'],.25,places=3)
            result=mix(root/'mixed.wav',cache)
            self.assertEqual(inspect_wav(result),55)
            legacy=dict(manifest,language='cs')
            (cache/'manifest.json').write_text(json.dumps(legacy))
            with self.assertRaisesRegex(ValueError,'not English'):validate(cache)
            (cache/'manifest.json').write_text(json.dumps(manifest))
            path=cache/'welcome.wav';path.write_bytes(path.read_bytes()+b'x')
            with self.assertRaisesRegex(ValueError,'checksum'):validate(cache)

    def test_missing_silent_and_oversized_audio_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            with self.assertRaises(ValueError):export(folder/'missing.mp4',audio_dir=folder)
            self.assertFalse((folder/'missing.mp4').exists())
            self.tone(folder/'silent.wav',silent=True)
            with self.assertRaisesRegex(ValueError,'silent'):inspect_wav(folder/'silent.wav')
            source=folder/'source';source.mkdir()
            for cue in SCRIPT['cues']:self.tone(source/(cue['id']+'.wav'),seconds=8)
            with self.assertRaisesRegex(ValueError,'needs'):prepare(folder/'cache',source_dir=source)

    def test_subtitles_are_english_ordered_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'demo.en.srt';subtitles(target);text=target.read_text()
            self.assertIn('Customer:',text);self.assertIn('CHERY Tiggo 8 Pro',text)
            self.assertIn('00:00:55,000',text)
            self.assertNotIn('Dobrý den',text)
            previous=0
            for cue in SCRIPT['cues']:
                self.assertGreaterEqual(cue['start'],previous)
                self.assertGreater(cue['end'],cue['start'])
                self.assertLessEqual(cue['end'],DURATION)
                previous=cue['end']
