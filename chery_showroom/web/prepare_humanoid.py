"""Export local Unitree G1 visual meshes and a neutral pose to self-contained GLB."""
import sys
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as E
import mujoco
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = Path(__file__).resolve().parent / 'public'
SOURCE = ROOT / 'unitree_mujoco/unitree_robots/g1'


def prepare():
    xml = E.parse(SOURCE / 'g1_29dof.xml')
    xml.find('compiler').set('meshdir', str(SOURCE / 'meshes'))
    model = mujoco.MjModel.from_xml_string(E.tostring(xml.getroot(), encoding='unicode'))
    data = mujoco.MjData(model)
    config = json.loads((ROOT / 'keyboard_walk/policy_config.json').read_text())
    sys.path.insert(0, str(ROOT))
    from benchmark_lab.core import NAMES
    joints = [model.jnt_qposadr[model.actuator(name).trnid[0]] for name in NAMES]
    for index, value in zip(config['joint_ids_map'], config['default_joint_pos']):
        data.qpos[joints[index]] = value
    mujoco.mj_forward(model, data)
    scene = trimesh.Scene()
    convert = trimesh.transformations.rotation_matrix(-np.pi/2, [1, 0, 0])
    scene.graph.update(frame_from='world', frame_to='G1', matrix=convert)
    def pose(position, rotation):
        matrix = np.eye(4); matrix[:3, :3] = rotation.reshape(3, 3); matrix[:3, 3] = position
        return matrix
    for body in range(1, model.nbody):
        parent = model.body_parentid[body]
        name = model.body(body).name
        world = pose(data.xpos[body], data.xmat[body])
        relative = np.linalg.inv(pose(data.xpos[parent], data.xmat[parent])) @ world if parent else world
        scene.graph.update(frame_from=model.body(parent).name if parent else 'G1', frame_to=name, matrix=relative)
    for geom in range(model.ngeom):
        if model.geom_type[geom] != mujoco.mjtGeom.mjGEOM_MESH or model.geom_contype[geom] != 0:
            continue
        mesh = model.geom_dataid[geom]; va = model.mesh_vertadr[mesh]; fa = model.mesh_faceadr[mesh]
        vertices = model.mesh_vert[va:va+model.mesh_vertnum[mesh]].copy()
        faces = model.mesh_face[fa:fa+model.mesh_facenum[mesh]].copy()
        geometry = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        geometry.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=model.mesh(mesh).name, baseColorFactor=np.round(model.geom_rgba[geom]*255).astype('uint8'),
            metallicFactor=.25, roughnessFactor=.4))
        body = model.geom_bodyid[geom]
        relative = np.linalg.inv(pose(data.xpos[body], data.xmat[body])) @ pose(data.geom_xpos[geom], data.geom_xmat[geom])
        scene.add_geometry(geometry, node_name=model.mesh(mesh).name+'_visual', parent_node_name=model.body(body).name, transform=relative)
    target = PUBLIC / 'models/g1-reception.glb'; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(scene.export(file_type='glb'))
    license_path = ROOT / 'unitree_mujoco/LICENSE'
    (PUBLIC / 'UNITREE_LICENSE.txt').write_bytes(license_path.read_bytes())
    sources = [SOURCE/'g1_29dof.xml', ROOT/'keyboard_walk/policy_config.json', license_path, *sorted((SOURCE/'meshes').glob('*.STL'))]
    manifest = dict(file='models/g1-reception.glb', sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        source='Local unitree_mujoco/unitree_robots/g1', license='BSD-3-Clause',
        copyright='2016-2024 HangZhou YuShu TECHNOLOGY CO.,LTD. (Unitree Robotics)',
        changes='Visual meshes only, neutral joint pose, Z-up to Y-up root, original metre scale; no collision geometry',
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        bounds=scene.bounds.tolist(), triangles=sum(len(g.faces) for g in scene.geometry.values()))
    (PUBLIC/'humanoid-assets.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['file','bounds','triangles']}))


if __name__ == '__main__': prepare()
