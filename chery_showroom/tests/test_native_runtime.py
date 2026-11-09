"""Acceptance of the existing showroom on native physics, without MuJoCo."""
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
import numpy as np
from chery_showroom.runtime import Showroom
from chery_showroom.layout import VEHICLE_SITES

class NativeShowroomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=Showroom()
    @classmethod
    def tearDownClass(cls):cls.app.close()
    def setUp(self):
        self.app.reset();self.app.commands.queue.clear()
    def tick(self):
        self.app.last_client=time.monotonic();self.app.tick()
        self.assertFalse(self.app.error,self.app.error)
        self.assertFalse(self.app.sim.snapshot()['fallen'])
    def command(self,action,car='tiggo8',text=''):
        self.app.command(dict(action=action,car=car,text=text));self.tick()
    def until(self,predicate,seconds=100):
        end=self.app.sim.data.time+seconds
        while not predicate():
            self.tick()
            self.assertLess(self.app.sim.data.time,end,str((self.app.phase,self.app.path,self.app.sim.data.qpos[:2])))
    def test_navigation_rejects_tangent_furniture_corner(self):
        self.assertFalse(self.app.navigator.segment_free([1.45,-2.25],[.7,-3]))
        start=np.array([4.75,-.31]);route=self.app.navigator.route(start,[0,-4.85])
        for point in route:
            self.assertTrue(self.app.navigator.segment_free(start,point));start=np.asarray(point)
        np.testing.assert_allclose(start,[0,-4.85])

    def test_native_import_boundary(self):
        code="""import builtins
original=builtins.__import__
def forbidden(name,*args,**kwargs):
 if name.split('.')[0]=='mujoco':raise AssertionError('MuJoCo dependency')
 return original(name,*args,**kwargs)
builtins.__import__=forbidden
from chery_showroom.runtime import Showroom
app=Showroom()
try:
 app.tick()
 assert app.state['backend']=='maloni-native'
 from chery_showroom.http_server import server
 from chery_showroom.voice import ShowroomProvider
 from chery_showroom.voice_assets import validate
finally:app.close()
"""
        subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,text=True,timeout=30)
    def test_stop_disconnect_and_reset_reject_stale_run(self):
        self.command('escort');self.assertTrue(self.app.path)
        old=self.app.run_id;self.app.last_client=time.monotonic()-3;self.app.tick()
        self.assertFalse(self.app.path);self.assertIn('connection',self.app.error.lower())
        self.command('reset');self.assertNotEqual(old,self.app.run_id)
        with self.assertRaises(ValueError):self.app.command(dict(action='escort',car='tiggo8',run_id=old))
        self.command('escort');self.command('stop');self.assertFalse(self.app.path);self.assertFalse(self.app.gesture_until)
    def test_escort_present_question_handoff(self):
        self.command('escort')
        self.until(lambda:self.app.phase=='arrived')
        goal=self.app.sim.model.site(VEHICLE_SITES['tiggo8']).pos[:2]
        self.assertLess(np.linalg.norm(self.app.sim.data.qpos[:2]-goal),.18)
        self.assertTrue(self.app.facing_vehicle('tiggo8'))
        for _ in range(75):self.tick()
        self.command('present');self.assertTrue(self.app.gesture_until)
        self.command('chat',text='How much does this car cost?')
        self.assertIn('verif',self.app.message);self.assertFalse(self.app.gesture_until)
        self.command('handoff');self.assertIn('booking',self.app.message.lower())
    def test_interactive_visit(self):
        from chery_showroom.visit_acceptance import connected_client
        with connected_client(self.app):
            self.command('interactive_start')
            self.until(lambda:self.app.interactive.stage=='choose',40)
            self.command('select',car='tiggo8')
            self.command('chat',text='yes')
            self.until(lambda:self.app.interactive.stage=='presentation',90)
            for part in range(3):
                self.assertEqual(self.app.interactive.part,part)
                if part<2:
                    for _ in range(220):self.tick()
                    self.command('interactive_continue')
            self.command('handoff');self.assertEqual(self.app.interactive.stage,'handoff')
            self.command('customer',text='exit')
            self.until(lambda:self.app.interactive.stage=='completed',180)

if __name__=='__main__':unittest.main()
