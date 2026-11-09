"""Scene portability, navigation clearances and robot dynamics regressions."""
import itertools,json,unittest
import xml.etree.ElementTree as E
from pathlib import Path
import mujoco
import numpy as np
from chery_showroom.scene import build,ROOT,SCENE
from chery_showroom.layout import WAYPOINTS,CAMERAS
from chery_showroom.navigation import Navigator

class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=mujoco.MjModel.from_xml_path(str(build()));cls.navigator=Navigator(cls.model)
    def test_required_sites_are_navigable_with_reserved_clearance(self):
        for start,end in itertools.combinations(WAYPOINTS,2):
            route=self.navigator.route(WAYPOINTS[start],WAYPOINTS[end]);last=WAYPOINTS[start]
            for point in route:self.assertTrue(self.navigator.segment_free(last,point),(start,end));last=point
    def test_astar_detours_around_reception(self):
        start=(-7.9,-2.0);target=(-2.2,-4.9)
        self.assertFalse(self.navigator.segment_free(start,target))
        route=self.navigator.route(start,target);self.assertGreater(len(route),1)
        for point in route:self.assertTrue(self.navigator.segment_free(start,point));start=point
    def test_concurrent_scene_builds_compile_without_partial_assets(self):
        import subprocess,sys
        code="from chery_showroom.scene import build; import mujoco,sys; q=sys.argv[1]; m=mujoco.MjModel.from_xml_path(str(build(q))); assert m.nq==36; assert m.vis.quality.offsamples==(2 if q=='interactive' else 4)"
        jobs=[subprocess.Popen([sys.executable,'-c',code,quality],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for quality in ('interactive','presentation')]
        for job in jobs:
            _,error=job.communicate(timeout=40);self.assertEqual(job.returncode,0,error.decode())
    def test_relative_assets_and_named_cameras(self):
        for file in (SCENE,SCENE.with_name('robot.xml')):
            for element in E.parse(file).iter():
                if element.get('file'):self.assertFalse(Path(element.get('file')).is_absolute(),element.get('file'))
        for name in CAMERAS:self.assertGreaterEqual(self.model.camera(name).id,0)
    def test_original_robot_dynamics_sensors_and_actuators_are_preserved(self):
        original=mujoco.MjModel.from_xml_path(str(ROOT/'unitree_mujoco/unitree_robots/g1/g1_29dof.xml'))
        for attr in ('nq','nv','nu','nsensor'):self.assertEqual(getattr(self.model,attr),getattr(original,attr))
        for attr in ('body_mass','body_inertia','dof_damping','dof_armature','actuator_gainprm','actuator_biasprm','jnt_range'):
            actual=getattr(self.model,attr)
            if attr.startswith('body_'):actual=actual[:original.nbody]
            np.testing.assert_allclose(actual,getattr(original,attr))
        self.assertEqual(self.model.body_mass[self.model.body('demo_customer').id],0)
        self.assertAlmostEqual(self.model.opt.timestep,original.opt.timestep)
    def test_adjacent_vehicles_have_one_point_five_metre_clearance(self):
        left=self.model.geom('tiggo4_collision');middle=self.model.geom('tiggo7_collision');right=self.model.geom('tiggo8_collision')
        for a,b in ((left,middle),(middle,right)):
            self.assertGreaterEqual(b.pos[0]-b.size[0]-(a.pos[0]+a.size[0]),1.5)
    def test_decor_has_no_contacts_and_floor_has_one_contact_surface(self):
        model=self.model;floor=model.geom('floor').id
        contacts=[i for i in range(model.ngeom) if model.geom_bodyid[i]==0 and (model.geom_contype[i] or model.geom_conaffinity[i])]
        for i in contacts:self.assertNotEqual(model.geom_type[i],mujoco.mjtGeom.mjGEOM_MESH)
        self.assertEqual(model.geom_size[floor,2],.08)
        self.assertEqual(model.geom_pos[floor,2]+model.geom_size[floor,2],0)
        for i in range(model.ngeom):
            if model.geom_bodyid[i]==0 and model.geom_group[i]==2:
                self.assertEqual(model.geom_contype[i],0);self.assertEqual(model.geom_conaffinity[i],0)
    def test_furniture_sources_are_documented(self):
        source=json.loads((SCENE.parent/'furnishings/provenance.json').read_text())
        self.assertEqual(len(source),2)
        for item in source:self.assertEqual(item['license'],'CC0-1.0');self.assertTrue(item['author']);self.assertTrue(item['files'])
