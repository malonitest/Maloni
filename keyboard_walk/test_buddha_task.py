"""Physical scene and task invariants; run with the workspace Python."""
import contextlib
import io
import json
from pathlib import Path
import unittest

import mujoco
import numpy as np

from buddha_task import BuddhaTask

ROOT = Path(__file__).resolve().parent.parent


class BuddhaTests(unittest.TestCase):
    def setUp(self):
        self.model = mujoco.MjModel.from_xml_path(str(ROOT/'unitree_mujoco/unitree_robots/g1/scene_lab_task.xml'))
        self.data = mujoco.MjData(self.model)
        cfg = json.loads((ROOT/'keyboard_walk/policy_config.json').read_text())
        self.default = np.empty(29)
        self.default[cfg['joint_ids_map']] = cfg['default_joint_pos']
        # Resolve named motors, independent of scene actuator count/order.
        names = ['left_'+p for p in ['hip_pitch','hip_roll','hip_yaw','knee','ankle_pitch','ankle_roll']]
        names += ['right_'+p for p in ['hip_pitch','hip_roll','hip_yaw','knee','ankle_pitch','ankle_roll']]
        names += ['waist_yaw','waist_roll','waist_pitch']
        names += [side+'_'+p for side in ['left','right'] for p in ['shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw']]
        self.act = np.array([self.model.actuator(n).id for n in names])
        self.qa = self.model.jnt_qposadr[self.model.actuator_trnid[self.act,0]]
        self.data.qpos[self.qa] = self.default
        mujoco.mj_forward(self.model,self.data)
        with contextlib.redirect_stdout(io.StringIO()):
            self.task = BuddhaTask(self.model,self.data,self.act,self.default,0)

    def test_100_ground_spawns_and_routes(self):
        positions = []
        for seed in range(100):
            with contextlib.redirect_stdout(io.StringIO()):
                self.task.reset(seed)
            t = self.task
            positions.append(t.spawn.copy())
            self.assertTrue(t.planner.clear(t.spawn,.7))
            self.assertGreaterEqual(np.linalg.norm(t.spawn-self.data.qpos[:2]),1.1)
            self.assertAlmostEqual(self.data.qpos[t.obj_q+2],.001)
            self.assertTrue(t.planner.path(self.data.qpos[:2],t.approach))
            self.assertTrue(t.planner.path(t.approach,[5.7,3.55]))
            # Settling must not expose an initial penetration or elevated spawn.
            for _ in range(10):
                mujoco.mj_step(self.model,self.data)
            self.assertLess(abs(self.data.qpos[t.obj_q+2]),.005)
            self.data.qpos[:7] = [0,0,.793,1,0,0,0]
            self.data.qpos[self.qa] = self.default
            self.data.qvel[:] = 0
            mujoco.mj_forward(self.model,self.data)
        self.assertEqual(len(np.unique(np.round(positions,4),axis=0)),100)

    def test_seed_reproducible_reset_clears_attachment(self):
        original = self.task.spawn.copy()
        self.data.eq_active[self.task.weld] = 1
        self.task.pause()
        with contextlib.redirect_stdout(io.StringIO()):
            self.task.reset(0)
        np.testing.assert_array_equal(original,self.task.spawn)
        self.assertFalse(self.task.attached)
        self.assertFalse(self.task.paused)
        self.assertEqual(self.task.state,'settle')

    def test_cannot_grasp_at_distance(self):
        self.assertFalse(self.task.attach())
        self.assertFalse(self.task.attached)

    def test_unreachable_goal_fails(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.task.route([5.7,4.65])
        self.assertEqual(self.task.state,'failed')
        self.assertFalse(self.task.success)

    def test_pause_preserves_hold_and_task_clock(self):
        self.task.state = 'carry'
        self.data.eq_active[self.task.weld] = 1
        self.task.pause()
        before = self.task.since
        self.data.time += 4
        command,_ = self.task.update(self.default,[4,-6,3])
        np.testing.assert_array_equal(command,[0,0,0])
        self.assertTrue(self.task.attached)
        self.task.resume()
        self.assertEqual(self.task.since,before+4)
        self.assertFalse(self.task.paused)

    def test_dropped_object_prevents_celebration(self):
        self.task.state = 'carry'
        with contextlib.redirect_stdout(io.StringIO()):
            self.task.update(self.default,[4,-6,3])
        self.assertEqual(self.task.state,'failed')
        self.assertFalse(self.task.success)

    def test_viewer_camera_position_uses_camera_side(self):
        from g1_keyboard import camera_world_position
        camera = mujoco.MjvCamera()
        camera.lookat[:] = [0,0,.9]
        camera.distance, camera.azimuth, camera.elevation = 4.4,55,-12
        np.testing.assert_allclose(camera_world_position(camera),[-2.46858663,-3.52550707,1.81481144],atol=1e-6)

    def test_camera_heading_from_current_position(self):
        self.task.transition('retreat')
        self.data.time += 3.1
        camera = np.array([-2.,3.,2.])
        self.task.update(self.default,camera)
        self.assertEqual(self.task.state,'face')
        self.assertAlmostEqual(self.task.face_heading,np.arctan2(camera[1]-self.data.qpos[1],camera[0]-self.data.qpos[0]))


if __name__ == '__main__':
    unittest.main()
