import time,unittest
import numpy as np
from chery_showroom.runtime import Showroom
from chery_showroom.scene import STOPS
from chery_showroom.sales import answer

class SalesTests(unittest.TestCase):
    def test_grounded_dialogue(self):
        self.assertEqual(answer('auto pro rodinu','tiggo4')[1],'tiggo4')
        self.assertEqual(answer('omezený rozpočet','tiggo7')[1],'tiggo7')
        self.assertEqual(answer('sedm míst','tiggo4')[1],'tiggo4')
        self.assertIn('do not have a verified',answer('kolik stojí','tiggo4')[0])
        self.assertIn('Tiggo 8',answer('porovnej vozy','tiggo4')[0])
        self.assertEqual(answer('zastav','tiggo4')[2],'stop')

class PhysicsTests(unittest.TestCase):
    def setUp(self):self.app=Showroom()
    def tearDown(self):self.app.close()
    def step(self,n):
        for _ in range(n):self.app.last_client=time.monotonic();self.app.tick();self.assertFalse(self.app.sim.snapshot()['fallen'])
    def test_routes_roundtrip(self):
        for car in ('tiggo4','tiggo7','tiggo8'):
            for action in ('escort','reception'):
                self.app.command(dict(action=action,car=car))
                for _ in range(5500):
                    self.step(1)
                    if not self.app.path:break
                self.assertEqual(self.app.phase,'arrived',self.app.error)
                goal=STOPS[car if action=='escort' else 'reception']
                self.assertLess(np.linalg.norm(self.app.sim.data.qpos[:2]-goal),.55)
                for k in range(self.app.sim.data.ncon):
                    c=self.app.sim.data.contact[k]
                    names=[self.app.sim.model.geom(g).name or '' for g in (c.geom1,c.geom2)]
                    self.assertFalse(any('collision' in n or 'stand' in n for n in names))
    def test_stop_stale_reset_and_gesture(self):
        a=self.app;a.command(dict(action='escort',car='tiggo7'));self.step(10)
        a.last_client=time.monotonic()-3;a.tick();self.assertFalse(a.path)
        a.command(dict(action='reset'));self.step(1);self.assertFalse(a.error)
        a.command(dict(action='escort',car='tiggo7'))
        for _ in range(5500):
            self.step(1)
            if not a.path:break
        self.assertEqual(a.phase,'arrived',a.error);self.step(40)
        a.command(dict(action='present',car='tiggo7'));self.step(30)
        self.assertTrue(a.gesture_until)
        a.command(dict(action='stop'));self.step(1);self.assertFalse(a.gesture_until)
        a.command(dict(action='present',car='tiggo7'));self.step(1);a.command(dict(action='reset'));self.step(1);self.assertEqual(a.phase,'greeting')
    def test_manual_keyboard_and_new_targets(self):
        app=self.app;start=app.sim.data.qpos[0];app.on_key(ord('W'));self.step(150)
        self.assertEqual(app.phase,'manual');self.assertGreater(app.sim.data.qpos[0],start+.1)
        app.on_key(32);self.step(1);self.assertFalse(np.any(app.manual));self.assertEqual(app.phase,'stopped')
        for target in ('entrance','reception','waiting_area'):
            app.command(dict(action='navigate',target=target))
            for _ in range(5000):
                self.step(1)
                if not app.path:break
            self.assertEqual(app.phase,'arrived',app.error)
            self.assertLess(np.linalg.norm(app.sim.data.qpos[:2]-app.sim.model.site(target).pos[:2]),.55)
        app.on_key(ord('R'));self.step(1);self.assertEqual(app.phase,'greeting')
    def test_validation(self):
        with self.assertRaises(ValueError):self.app.command(dict(action='drive'))
        with self.assertRaises(ValueError):self.app.command(dict(action='escort',car='unknown'))
if __name__=='__main__':unittest.main()

class VoiceTests(unittest.TestCase):
    def test_missing_backend_and_invalid_response(self):
        from chery_showroom.voice import ShowroomProvider
        from unittest.mock import patch,MagicMock
        with self.assertRaises(ValueError):ShowroomProvider(key='').create('sdp',{})
        reply=MagicMock();reply.__enter__.return_value.read.return_value=b'{}'
        with patch('chery_showroom.voice.urlopen',return_value=reply):
            with self.assertRaises(RuntimeError):ShowroomProvider(key='test').create('sdp',{})
    def test_no_unrequested_actions(self):
        self.assertIsNone(answer('Neukazuj mi auto','tiggo4')[2])
        self.assertEqual(answer('mám rozpočet 800000','tiggo7')[1],'tiggo7')
