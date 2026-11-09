import copy
import unittest
import numpy as np
from chery_showroom.shared_scene import scene_definition,world_object,waypoint,collision_boxes,validate
from chery_showroom.native_scene import robot_scene,navigation
from chery_showroom.web_assets import layout_payload

class SharedSceneTests(unittest.TestCase):
    def test_counter_moves_desk_robot_customer_and_reception_together(self):
        original=scene_definition();edited=copy.deepcopy(original);edited['objects']['reception_counter']['position'][0]+=.25
        for name in ['staff_desk','robot_reception','customer_reception']:
            a=world_object(original,name);b=world_object(edited,name)
            np.testing.assert_allclose(np.array(b['position'])-a['position'],[.25,0,0])
        self.assertAlmostEqual(waypoint(edited,'reception')[0]-waypoint(original,'reception')[0],.25)
    def test_chair_pose_drives_http_and_native_rotated_collider(self):
        scene=scene_definition();chair=scene['objects']['left_lounge_chair'];chair['position'][0]+=.3;chair['yaw']+=.2
        public=layout_payload(scene);self.assertEqual(public['scene']['objects']['left_lounge_chair'],chair)
        physics=robot_scene(scene);index=physics['static_object_ids'].index('left_lounge_chair');points=np.array(physics['static_colliders'][index]['points'])
        box=next(x for x in public['collision_boxes'] if x['id']=='left_lounge_chair')
        np.testing.assert_allclose(points.mean(axis=0),box['position'],atol=1e-12)
        self.assertAlmostEqual(box['position'][0],2.45)
        self.assertGreater(np.ptp(points[:,0]),.8)
    def test_waiting_waypoint_does_not_intersect_visible_coffee_table(self):
        scene=scene_definition();nav=navigation(scene)
        self.assertFalse(nav.free([3.3,-3.5]))
        self.assertTrue(nav.free(waypoint(scene,'waiting_area')[:2]))
    def test_recovery_exits_margin_but_rejects_physical_obstacle(self):
        nav=navigation();start=[-2.25052635,-1.57763152]
        self.assertFalse(nav.free(start))
        with self.assertRaises(ValueError):nav.route(start,[-6.3,.1])
        route=nav.route(start,[-6.3,.1],allow_recovery=True)
        self.assertTrue(nav.last_recovery);self.assertTrue(nav.free(route[0]))
        from chery_showroom.navigation import Navigator
        tight=Navigator(obstacles=nav.obstacles,bounds=nav.bounds,clearance=nav.clearance-.10)
        self.assertTrue(tight.segment_free(start,route[0]))
        with self.assertRaises(ValueError):nav.route([-2.2,-2.1],[-6.3,.1],allow_recovery=True)

    def test_default_design_and_asset_dimensions_unchanged(self):
        scene=scene_definition()
        self.assertEqual(world_object(scene,'reception_counter')['position'],[-2.2,-2.7,.55])
        self.assertEqual(world_object(scene,'left_lounge_chair')['position'],[2.15,-3.3,.012])
        self.assertEqual([v['length'] for v in layout_payload(scene)['vehicles']],[4.48,4.69,4.72])
    def test_scene_validation_rejects_cycles_and_nonfinite_geometry(self):
        scene=scene_definition();scene['objects']['staff_desk']['parent']='staff_desk'
        with self.assertRaises(ValueError):validate(scene)
        scene=scene_definition();scene['objects']['staff_desk']['size'][0]=float('nan')
        with self.assertRaises(ValueError):validate(scene)
