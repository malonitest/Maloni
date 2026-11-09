import time
import unittest
from unittest.mock import patch
import numpy as np
from chery_showroom.controller import Showroom

class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=Showroom()
    @classmethod
    def tearDownClass(cls):cls.app.close()
    def setUp(self):self.app.reset();self.app.commands.queue.clear();self.free=patch.object(self.app.navigator,'segment_free',return_value=True);self.free.start();self.addCleanup(self.free.stop)
    def tick(self):self.app.last_client=time.monotonic();self.app.tick()
    def packet(self,seq=0,**extra):
        value=dict(action='manual_control',run_id=self.app.run_id,sequence=seq,vx=.1,vy=0,yaw_rate=0);value.update(extra);return value
    def test_validation_and_order(self):
        for values in [dict(vx=float('nan')),dict(sequence=1.5),dict(run_id='old'),dict(vy='bad'),dict(vx=[1],vy=[0],yaw_rate=[0]),dict(vx=True)]:
            with self.assertRaises(ValueError):self.app.command(self.packet(**values))
        self.app.command(self.packet());self.tick()
        with self.assertRaises(ValueError):self.app.command(self.packet())
        self.assertEqual(self.app.state['control_mode'],'manual')
        self.assertEqual(self.app.state['diagnostics']['velocity_frame'],'robot')
    def test_lease_expiry_and_stale_queue(self):
        self.app.command(self.packet());self.tick()
        self.app.manual_deadline=time.monotonic()-.001;self.tick()
        np.testing.assert_array_equal(self.app.manual,0)
        self.assertFalse(self.app.state['manual_control']['valid'])
        with self.assertRaises(ValueError):self.app.command(self.packet(1))
        with patch('chery_showroom.controller.time.monotonic',return_value=time.monotonic()-.5):self.app.command(self.packet(1,begin=True))
        self.tick();np.testing.assert_array_equal(self.app.manual,0)
        latency=self.app.manual_stop_latency_ms
        self.app.command(self.packet(2,vx=0));self.tick()
        self.assertEqual(self.app.manual_stop_latency_ms,latency)
        self.app.command(self.packet(3,begin=True));self.tick()
        self.assertTrue(self.app.state['manual_control']['valid'])
    def test_visit_fault_and_generation(self):
        self.app.interactive.active=True
        with self.assertRaises(ValueError):self.app.command(self.packet())
        self.app.interactive.active=False;self.app.error='fault'
        with self.assertRaises(ValueError):self.app.command(self.packet())
        self.app.error='';self.app.command(self.packet());self.app.new_visit();self.tick()
        np.testing.assert_array_equal(self.app.manual,0)
    def test_release_stop_and_limits(self):
        self.app.command(self.packet(vx=10,vy=-10,yaw_rate=10));self.tick()
        np.testing.assert_allclose(self.app.manual,[.5,-.2,.2])
        self.app.command(self.packet(1,vx=0));self.tick()
        self.assertEqual(self.app.phase,'stopped')
        np.testing.assert_array_equal(self.app.manual,0)
    def test_obstacle_stops_manual(self):
        self.app.command(self.packet())
        with patch.object(self.app.navigator,'segment_free',return_value=False):self.tick()
        self.assertEqual(self.app.failure_code,'blocked')
        np.testing.assert_array_equal(self.app.manual,0)

if __name__=='__main__':unittest.main()
