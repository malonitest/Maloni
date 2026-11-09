import hashlib,json,unittest
from pathlib import Path
import mujoco
import numpy as np
from chery_showroom.library_models import LIBRARY,MODELS
from chery_showroom.scene import SCENE,CARS
from chery_showroom.sales import answer

class ImportedModelTests(unittest.TestCase):
    def test_source_integrity_and_attribution(self):
        for item in json.loads((LIBRARY/'provenance.json').read_text())['models']:
            self.assertEqual(hashlib.sha256((LIBRARY/item['file']).read_bytes()).hexdigest(),item['sha256'])
            self.assertEqual(item['license'],'CC-BY-4.0')
            self.assertIn('source',item['embedded_credit'])
    def test_visual_geometry_inside_collision_envelopes(self):
        model=mujoco.MjModel.from_xml_path(str(SCENE))
        for key,(name,_) in MODELS.items():
            manifest=json.loads((LIBRARY/(name+'.json')).read_text());x,y,_=CARS[key]
            collision=model.geom(key+'_collision')
            for i,_ in enumerate(manifest['parts']):
                geom=model.geom(key+'_reference_'+str(i));mesh=model.geom_dataid[geom.id]
                vertices=model.mesh_vert[model.mesh_vertadr[mesh]:model.mesh_vertadr[mesh]+model.mesh_vertnum[mesh]]
                rotation=np.empty(9);mujoco.mju_quat2Mat(rotation,model.geom_quat[geom.id])
                vertices=vertices@rotation.reshape(3,3).T+model.geom_pos[geom.id]
                self.assertTrue(np.all(np.abs(vertices-np.array([x,y,.85]))<=collision.size+1e-3),key)
    def test_proxy_identity_is_disclosed(self):
        reply,_,_=answer('Jaké auto je vystavené?','tiggo4');self.assertIn('BMW X1',reply)
        reply,_,_=answer('Jaký model je vystavený?','tiggo7');self.assertIn('Volvo XC60',reply)
        reply,selected,action=answer('Zaveď mě k Tiggo 4','tiggo8');self.assertEqual(selected,'tiggo8');self.assertIsNone(action)
