"""Acceptance of independent MALONI drive, contacts, dialogue and G1 isolation."""
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from chery_showroom.maloni120_simulation import Simulation
from chery_showroom.controller import Showroom
from chery_showroom.reception import ReceptionDesk

class DriveTests(unittest.TestCase):
    def setUp(self):self.sim=Simulation()
    def tearDown(self):self.sim.close()
    def run_steps(self,cmd,count):
        for _ in range(count):self.sim.step(cmd)
    def test_independence_acceleration_and_braking(self):
        with patch('chery_showroom.native_scene._robot_model',side_effect=AssertionError('G1 model must not load')),patch('subprocess.Popen',side_effect=AssertionError('No policy process')):
            sim=Simulation();initial=sim.xy.copy();sim.step([.4,0,0])
            self.assertGreater(sim.speed,0);self.assertLess(sim.speed,.4)
            self.assertLess(np.linalg.norm(sim.xy-initial),.008)
            for _ in range(50):sim.step([.3,0,0])
            self.assertGreater(sim.speed,.2);sim.emergency_stop()
            for _ in range(100):sim.step([.4,0,.5])
            self.assertLess(abs(sim.speed),.001);self.assertLess(abs(sim.omega),.001)
            self.assertTrue(sim.emergency_stopped);sim.reset();self.assertFalse(sim.emergency_stopped)
    def test_no_strafe_and_turn_in_place(self):
        start=self.sim.xy.copy();self.run_steps([0,.3,0],100)
        np.testing.assert_allclose(self.sim.xy,start)
        yaw=self.sim.yaw;self.run_steps([0,0,.5],100)
        np.testing.assert_allclose(self.sim.xy,start,atol=1e-10)
        self.assertGreater(abs(self.sim.yaw-yaw),.5)
        self.assertAlmostEqual(self.sim.wheel_speeds.sum(),0)
    def test_torque_and_traction_limits(self):
        self.sim.friction=.01;self.sim.step([.4,0,0])
        p=self.sim.parameters
        self.assertLessEqual(max(abs(self.sim.torques)),p['motor_torque_limit'])
        self.assertLess(self.sim.speed,.01)
    def test_static_contact_prevents_penetration(self):
        self.sim.obstacles=[('wall',[.2,3.,2.],[0,0,1.],.3)]
        self.sim.xy=np.array([-1.,0.]);self.sim.yaw=0.;self.sim._sync()
        touched=False
        for _ in range(400):
            self.sim.step([.4,0,0]);touched |= self.sim.contact_count>0
            self.assertIsNone(self.sim._contact(self.sim.xy))
        self.assertTrue(touched);self.assertLess(self.sim.xy[0],-.4)
    def test_gestures_limits_and_determinism(self):
        a=Simulation(seed=4,joint_noise=.01);b=Simulation(seed=4,joint_noise=.01)
        for _ in range(100):
            for s in (a,b):s.gesture('greet',2,2);s.step([0,0,0])
        np.testing.assert_array_equal(a.joints,b.joints)
        self.assertGreater(a.joints[7],.4);limits=np.array(a.parameters['joint_limits'])
        self.assertTrue(np.all(a.joints>=limits[:,0]));self.assertTrue(np.all(a.joints<=limits[:,1]))
        for bad in ([float('nan'),0,0],[1,2],[0,float('inf'),0]):
            with self.assertRaises(ValueError):a.step(bad)

class ShowroomTests(unittest.TestCase):
    def setUp(self):self.app=Showroom(robot_model='maloni120',language='cs')
    def tearDown(self):self.app.close()
    def tick(self):self.app.last_client=time.monotonic();self.app.tick()
    def test_dialogue_reception_and_emergency(self):
        self.app.command(dict(action='chat',text='Kdo jsi?'));self.tick()
        self.assertIn('MALONI Humanoid 120',self.app.state['message'])
        desk=ReceptionDesk();result=desk.respond(dict(text='Jak chodí robot?',car='tiggo4',run_id=self.app.run_id),self.app.run_id,'cs',dict(robot_model='maloni120'))
        self.assertIn('hnacími koly',result['reply'])
        self.app.command(dict(action='emergency_stop'));self.tick()
        self.assertTrue(self.app.sim.emergency_stopped);self.assertEqual(self.app.failure_code,'emergency_stop')
        self.assertIn('Nouzové',self.app.state['error'])
        self.app.command(dict(action='reset'));self.tick();self.assertFalse(self.app.sim.emergency_stopped)
    def test_navigation_and_return(self):
        for target in ('vehicle_3','reception'):
            self.app.command(dict(action='navigate',target=target))
            for _ in range(7000):
                self.tick()
                if self.app.error or self.app.phase=='arrived':break
            self.assertFalse(self.app.error,self.app.error);self.assertEqual(self.app.phase,'arrived',target)
            self.assertLess(np.linalg.norm(self.app.sim.xy-self.app.sim.model.site(target).pos[:2]),.25)
            self.assertEqual(self.app.state['robot_model'],'maloni120')
    def test_disconnect_brakes(self):
        self.app.manual[:]=[.3,0,0];self.app.phase='manual';self.app.manual_deadline=time.monotonic()+10
        self.app.sim.xy=np.array([0.,-3.]);self.app.sim.yaw=0.;self.app.sim._sync()
        for _ in range(20):self.tick()
        self.app.last_client=time.monotonic()-5
        self.app.tick()
        self.assertEqual(self.app.failure_code,'disconnected')
        for _ in range(100):self.tick()
        self.assertLess(abs(self.app.sim.speed),.001)

if __name__=='__main__':unittest.main()
