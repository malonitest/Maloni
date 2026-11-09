import unittest
import mujoco
import numpy as np
from chery_showroom.cinematic import camera_pose,update,DURATION
from chery_showroom.scene import SCENE

class CinematicTests(unittest.TestCase):
    def test_camera_loop_is_continuous_and_at_eye_level(self):
        for t in np.linspace(0,DURATION,401):
            pos,quat=camera_pose(t)
            self.assertTrue(np.isfinite(pos).all());self.assertTrue(np.isfinite(quat).all())
            self.assertAlmostEqual(np.linalg.norm(quat),1)
            self.assertGreater(pos[2],1.1);self.assertLess(pos[2],2.0)
            self.assertLess(pos[1],-.8);self.assertGreater(pos[1],-2.5)
        for a,b in zip(camera_pose(0),camera_pose(DURATION)):np.testing.assert_allclose(a,b)
        before=camera_pose(DURATION-.001)[0];after=camera_pose(.001)[0]
        self.assertLess(np.linalg.norm(before-after),.01)
    def test_camera_update_keeps_physics_unchanged(self):
        model=mujoco.MjModel.from_xml_path(str(SCENE));data=mujoco.MjData(model);mujoco.mj_forward(model,data)
        qpos=data.qpos.copy();qvel=data.qvel.copy();update(model,data,12)
        np.testing.assert_array_equal(data.qpos,qpos);np.testing.assert_array_equal(data.qvel,qvel)
        expected,_=camera_pose(12);np.testing.assert_allclose(data.cam_xpos[model.camera('cinematic').id],expected)
