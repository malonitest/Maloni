"""Shared converted Poly Haven furniture; metre scale, retained UVs and provenance."""
from pathlib import Path
import json,math,os
import xml.etree.ElementTree as E
BASE=Path(__file__).with_name('assets')/'furnishings'

def convert():
    """Developer-only conversion. Runtime uses the preconverted OBJ/PNG assets."""
    import trimesh
    import numpy as np
    from PIL import Image
    for item in json.loads((BASE/'provenance.json').read_text()):
        directory=BASE/item['name'];scene=trimesh.load(directory/(item['name']+'.gltf'),force='scene',process=False)
        parts=[];bounds=[]
        for index,node in enumerate(scene.graph.nodes_geometry):
            transform,key=scene.graph[node];g=scene.geometry[key].copy();g.apply_transform(transform)
            g.vertices=g.vertices@np.array([[1,0,0],[0,0,-1],[0,1,0]]).T
            # Keep the source scale and place the object's lowest vertex on the floor.
            bounds.extend(g.vertices.tolist());material=g.visual.material;name=material.name
            filename=f'part_{index}.obj';(directory/filename).write_text(trimesh.exchange.obj.export_obj(g,include_texture=True,write_texture=False))
            maps={}
            for path in (directory/'textures').glob(name+'_*_1k.jpg'):
                role=path.name.removeprefix(name+'_').removesuffix('_1k.jpg')
                if role not in ('diff','nor_gl','arm','rough'):continue
                target=name+'_'+role+'.png';Image.open(path).convert('RGB').save(directory/target);maps[role]=target
            parts.append(dict(file=filename,maps=maps,name=name))
        (directory/'converted.json').write_text(json.dumps(dict(parts=parts,bounds=[np.min(bounds,0).tolist(),np.max(bounds,0).tolist()]),indent=2)+'\n')

def add_furnishings(asset,world,geom):
    def add(name,position,yaw,label):
        directory=BASE/name;manifest=json.loads((directory/'converted.json').read_text())
        for index,part in enumerate(manifest['parts']):
            shared=f'{name}_{index}'
            if asset.find(f"mesh[@name='{shared}']") is None:
                E.SubElement(asset,'mesh',name=shared,file=os.path.relpath(directory/part['file'],BASE.parent))
                material=E.SubElement(asset,'material',name=shared,rgba='1 1 1 1',specular='.18',shininess='.3',metallic='0',roughness='.65')
                for role,file in part['maps'].items():
                    texture=shared+'_'+role
                    E.SubElement(asset,'texture',name=texture,type='2d',file=os.path.relpath(directory/file,BASE.parent))
                    if role=='diff':E.SubElement(material,'layer',role='rgb',texture=texture)
                    elif role=='nor_gl':E.SubElement(material,'layer',role='normal',texture=texture)
                    elif role=='arm':E.SubElement(material,'layer',role='orm',texture=texture)
                    elif role=='rough':E.SubElement(material,'layer',role='roughness',texture=texture)
            z=position[2]-manifest['bounds'][0][2]
            E.SubElement(world,'geom',name=label+'_'+str(index),type='mesh',mesh=shared,material=shared,pos=f'{position[0]} {position[1]} {z}',euler=f'0 0 {yaw}',contype='0',conaffinity='0',group='2')
        # AABB of the rotated source model, with a small inset for soft edges.
        import numpy as np
        low,high=np.array(manifest['bounds']);c,s=math.cos(yaw),math.sin(yaw)
        corners=np.array([[a,b] for a in (low[0],high[0]) for b in (low[1],high[1])])@np.array([[c,s],[-s,c]])
        mn,mx=corners.min(0),corners.max(0);center=(mn+mx)/2;size=(mx-mn)/2
        geom(label+'_collision',(position[0]+center[0],position[1]+center[1],(high[2]-low[2])/2),(*size,(high[2]-low[2])/2),'dark',collision=True,rgba='0 0 0 0',group='5')
    # Replace the old block seating and procedural indoor plants only.
    prefixes=('sofa','backrest','chair','pot-','pot7','plant-','plant7')
    for g in list(world.findall('geom')):
        if g.get('name','').startswith(prefixes) or g.get('name','').startswith('plant_'):world.remove(g)
    add('modern_arm_chair_01',(5.5,-3.7,0),math.pi/2,'lounge_chair_left')
    add('modern_arm_chair_01',(7.5,-3.7,0),-math.pi/2,'lounge_chair_right')
    for x in (-7,7):
        add('modern_arm_chair_01',(x-1.2,5.8,0),math.pi/2,'consult_left_'+str(x))
        add('modern_arm_chair_01',(x+1.2,5.8,0),-math.pi/2,'consult_right_'+str(x))
    for x in (-7,7):add('potted_plant_02',(x,-5,0),0,'indoor_plant_'+str(x))
def restore(check=False):
    import hashlib
    from urllib.request import urlopen
    for item in json.loads((BASE/'provenance.json').read_text()):
        for record in item['files']:
            target=BASE/item['name']/record['file']
            if not target.exists():
                if check:raise FileNotFoundError(target)
                with urlopen(record['url'],timeout=60) as response:data=response.read()
                if hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Source checksum mismatch')
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            if hashlib.sha256(target.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Local source modified: '+str(target))
    print('Furniture source checksums verified.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--restore',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check or args.restore:restore(args.check)
    else:convert()

