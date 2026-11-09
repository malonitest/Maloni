"""Strict, offline MJCF-subset conversion. Does not import the MuJoCo library.

Ground-only conversion is an explicit diagnostic mode, never a full-physics claim.
"""
import argparse
import copy
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import numpy as np

class ImportFailure(ValueError): pass

def values(element,key,default,n=None):
    result=[float(v) for v in element.get(key,default).split()]
    if (n is not None and len(result)!=n) or not np.isfinite(result).all():
        raise ImportFailure(f'{element.tag} {element.get("name", "")}: invalid {key}')
    return result

def rotation(q):
    q=np.asarray(q,dtype=float);norm=np.linalg.norm(q)
    if norm<1e-12: raise ImportFailure('Zero quaternion')
    w,x,y,z=q/norm
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def stl_vertices(path):
    data=path.read_bytes()
    if len(data)>=84 and 84+50*struct.unpack_from('<I',data,80)[0]==len(data):
        n=struct.unpack_from('<I',data,80)[0]
        points=np.ndarray((n,3,3),dtype='<f4',buffer=data,offset=96,strides=(50,12,4)).reshape(-1,3).astype(float)
    else:
        points=np.array([[float(v) for v in line.split()[1:]] for line in data.decode('ascii').splitlines() if line.strip().startswith('vertex ')])
    if points.ndim!=2 or points.shape[1]!=3 or not len(points) or not np.isfinite(points).all():
        raise ImportFailure(f'Invalid STL: {path}')
    return np.unique(points,axis=0)

# Attributes which actually affect the supported physics must be translated or rejected.
ATTRS={
 'body':{'name','pos','quat','childclass'},
 'inertial':{'pos','quat','mass','diaginertia','fullinertia'},
 'joint':{'name','type','pos','axis','range','limited','class','damping','frictionloss','armature','actuatorfrcrange','actuatorfrclimited'},
 'geom':{'name','type','size','pos','quat','mesh','class','contype','conaffinity','group','density','rgba','material','friction','condim','priority','solref','solimp','margin'},
 'compiler':{'angle','meshdir','autolimits'},
 'option':{'timestep','gravity','integrator','solver','iterations'},
}

def check(e):
    unknown=set(e.attrib)-ATTRS.get(e.tag,set(e.attrib))
    if unknown: raise ImportFailure(f'{e.tag} {e.get("name", "")}: unsupported attributes {sorted(unknown)}')

def convert(path,contact_scope='full'):
    path=Path(path).resolve()
    roots=[];seen=set()
    def load(p):
        if p in seen: raise ImportFailure(f'Circular or repeated include: {p}')
        seen.add(p)
        root=ET.parse(p).getroot()
        if root.tag!='mujoco': raise ImportFailure(f'Not MJCF: {p}')
        for e in root:
            if e.tag=='include':load((p.parent/e.attrib['file']).resolve())
        roots.append((p,root))
    load(path)
    defaults={'':{}};meshes={};bodies=[];world_elements=[];motors=[];sensors=[]
    dt=.002;gravity=[0,0,-9.81];ground=False;ground_friction=1.;warnings=[]
    supported={'compiler','default','asset','worldbody','option','actuator','sensor','visual','statistic','include','keyframe'}
    def default(e,parent=''):
        name=e.get('class',parent);defaults[name]=copy.deepcopy(defaults.get(parent,{}))
        for child in e:
            if child.tag!='default': defaults[name][child.tag]=dict(child.attrib)
        for child in e:
            if child.tag=='default': default(child,name)
    for source,root in roots:
        for e in root:
            if e.tag not in supported: raise ImportFailure(f'{source}: unsupported element <{e.tag}>')
            if e.tag=='default': default(e)
    def effective(e,cls=''):
        cls=e.get('class',cls)
        if cls not in defaults: raise ImportFailure(f'Unknown default class {cls}')
        attrs=dict(defaults[cls].get(e.tag,{}));attrs.update(e.attrib)
        result=ET.Element(e.tag,attrs);check(result);return result
    for source,root in roots:
        compiler=root.find('compiler');meshdir=source.parent
        if compiler is not None:
            check(compiler)
            if compiler.get('angle','degree')!='radian': raise ImportFailure('Only explicit radian angle units supported')
            meshdir=source.parent/compiler.get('meshdir','')
        for e in root:
            if e.tag=='option':
                check(e);dt=values(e,'timestep',str(dt),1)[0];gravity=values(e,'gravity','0 0 -9.81',3)
                if set(e.attrib)&{'integrator','solver','iterations'}: warnings.append('Original solver settings replaced by MALONI solver; not numerically equivalent')
            elif e.tag=='asset':
                for a in e:
                    if a.tag=='mesh':
                        if set(a.attrib)-{'name','file','scale'}: raise ImportFailure(f'Unsupported mesh attributes: {a.attrib}')
                        meshes[a.attrib['name']]=(meshdir/a.attrib['file'],values(a,'scale','1 1 1',3))
                    elif a.tag not in {'texture','material'}:raise ImportFailure(f'Unsupported asset {a.tag}')
            elif e.tag=='worldbody':world_elements.extend(e)
            elif e.tag=='actuator':motors.extend(e)
            elif e.tag=='sensor':sensors.extend(e)
    joint_names=[]
    def parse_body(raw,parent=-1,cls=''):
        b=effective(raw,cls);cls=b.get('childclass',cls)
        inertial=raw.find('inertial')
        if inertial is None:raise ImportFailure(f'{b.get("name")}: explicit inertial required')
        check(inertial)
        if 'fullinertia' in inertial.attrib:
            xx,yy,zz,xy,xz,yz=values(inertial,'fullinertia','',6);inertia=np.array([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]])
        else:inertia=np.diag(values(inertial,'diaginertia','',3))
        r=rotation(values(inertial,'quat','1 0 0 0',4));inertia=r@inertia@r.T
        out=dict(name=b.attrib['name'],parent=parent,mass=values(inertial,'mass','',1)[0],
            offset=values(b,'pos','0 0 0',3),quaternion=values(b,'quat','1 0 0 0',4),
            com=values(inertial,'pos','0 0 0',3),inertia=inertia.tolist(),colliders=[],visuals=[])
        joints=[effective(j,cls) for j in raw if j.tag in {'joint','freejoint'}]
        if len(joints)>1:raise ImportFailure(f'{out["name"]}: multiple joints per body unsupported')
        if parent<0:
            if not joints or joints[0].get('type')!='free':raise ImportFailure('Root must have a free joint')
            out['root_position']=out['offset'];out['offset']=[0,0,0]
        elif joints:
            j=joints[0]
            if j.get('type','hinge')!='hinge':raise ImportFailure('Only hinge joints supported')
            if values(j,'pos','0 0 0',3)!=[0,0,0]:raise ImportFailure(f'{j.get("name")}: off-origin hinge unsupported')
            lim=values(j,'range','-1e30 1e30',2) if j.get('limited')!='false' else [-1e30,1e30]
            effort_range=values(j,'actuatorfrcrange','-1e30 1e30',2)
            if effort_range[0]!=-effort_range[1]:raise ImportFailure('Asymmetric joint force limits unsupported')
            out['joint']=dict(name=j.attrib['name'],type='hinge',axis=values(j,'axis','0 0 1',3),range=lim,
                damping=values(j,'damping','0',1)[0],friction=values(j,'frictionloss','0',1)[0],armature=values(j,'armature','0',1)[0],
                effort=max(abs(x) for x in values(j,'actuatorfrcrange','-1e30 1e30',2)))
            joint_names.append(j.attrib['name'])
        for child in raw:
            if child.tag not in {'body','geom','inertial','joint','freejoint','site'}:raise ImportFailure(f'Unsupported body child {child.tag}')
            if child.tag!='geom':continue
            g=effective(child,cls);kind=g.get('type','sphere');pos=np.array(values(g,'pos','0 0 0',3));r=rotation(values(g,'quat','1 0 0 0',4))
            visual=dict(type=kind,position=pos.tolist(),quaternion=values(g,'quat','1 0 0 0',4))
            if kind=='mesh':
                name=g.attrib['mesh']
                if name not in meshes:raise ImportFailure(f'Unknown mesh {name}')
                file,scale=meshes[name];visual.update(file=str(file),scale=scale)
            elif kind in {'sphere','box','cylinder'}:visual['size']=values(g,'size','',{'sphere':1,'box':3,'cylinder':2}[kind])
            else:raise ImportFailure(f'Unsupported geom type {kind}')
            out['visuals'].append(visual)
            if int(g.get('contype','1'))==0 and int(g.get('conaffinity','1'))==0:continue
            if contact_scope=='full' and (int(g.get('contype','1'))!=1 or int(g.get('conaffinity','1'))!=1):raise ImportFailure('Custom collision masks unsupported')
            if set(g.attrib)&{'solref','solimp','condim','priority','margin'}:raise ImportFailure('Custom contact parameters unsupported')
            size=visual.get('size',[]);radius=0
            if kind=='mesh':
                if file.suffix.lower()!='.stl':raise ImportFailure(f'Collision mesh must be STL: {file}')
                points=stl_vertices(file)*scale
            elif kind=='sphere':points=np.zeros((1,3));radius=size[0]
            elif kind=='box':points=np.array([[x,y,z] for x in [-size[0],size[0]] for y in [-size[1],size[1]] for z in [-size[2],size[2]]])
            else:
                out['colliders'].append(dict(type='cylinder',center=pos.tolist(),axis=r[:,2].tolist(),radius=size[0],half_length=size[1],friction=values(g,'friction','1 .005 .0001')[0]));continue
            out['colliders'].append(dict(points=(points@r.T+pos).tolist(),radius=radius,friction=values(g,'friction','1 .005 .0001')[0]))
        idx=len(bodies);bodies.append(out)
        for child in raw.findall('body'):parse_body(child,idx,cls)
    for e in world_elements:
        if e.tag=='body':
            if bodies:raise ImportFailure('Multiple free trees/static bodies not implemented')
            parse_body(e)
        elif e.tag=='geom':
            e=effective(e)
            if set(e.attrib)&{'solref','solimp','condim','priority','margin'}:raise ImportFailure('Custom ground contact parameters unsupported')
            if ground:raise ImportFailure('Multiple world planes unsupported')
            ground_friction=values(e,'friction','1 .005 .0001')[0]
            if e.get('type')!='plane' or values(e,'pos','0 0 0',3)!=[0,0,0] or values(e,'quat','1 0 0 0',4)!=[1,0,0,0]:raise ImportFailure('Only horizontal world plane at z=0 supported')
            ground=True
        elif e.tag not in {'light','camera','site'}:raise ImportFailure(f'Unsupported world element {e.tag}')
    actuator_names=[]
    for motor in motors:
        if motor.tag!='motor' or set(motor.attrib)-{'name','joint','gear','ctrllimited','ctrlrange'}:raise ImportFailure(f'Unsupported actuator {motor.tag} {motor.attrib}')
        if values(motor,'gear','1',1)!=[1]:raise ImportFailure('Only unit motor gear supported')
        if motor.get('joint') not in joint_names:raise ImportFailure('Unknown actuator joint')
        actuator_names.append(dict(name=motor.get('name',motor.attrib['joint']),joint=motor.attrib['joint'],ctrlrange=values(motor,'ctrlrange','-1e30 1e30',2)))
    for s in sensors:
        if s.tag not in {'jointpos','jointvel','jointactuatorfrc','framequat','framepos','framelinvel','gyro','accelerometer'}:raise ImportFailure(f'Unsupported sensor {s.tag}')
    if not bodies:raise ImportFailure('No dynamic bodies')
    if ground:
        for body in bodies:
            for collider in body['colliders']:collider['friction']=max(collider['friction'],ground_friction)
    root=bodies[0]
    return dict(version=1,name=path.stem,source=str(path),timestep=dt,gravity=gravity,ground=ground,
        position=root.pop('root_position'),orientation=root['quaternion'],bodies=bodies,actuators=actuator_names,
        sensors=[dict(type=s.tag,**s.attrib) for s in sensors],requires=['articulated_tree','plane_contacts']+(['body_contacts'] if contact_scope=='full' else []),
        limitations=(['ground-only contacts; no self collisions or body-to-body contacts'] if contact_scope=='ground-only' else ['one articulated tree only; no independent objects or fixed constraints'])+['IMU acceleration, contact parameters and solver are not equivalent to MuJoCo'],warnings=warnings)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--contact-scope',choices=['full','ground-only'],default='full');a=p.parse_args()
    try:scene=convert(a.source,a.contact_scope)
    except (ImportFailure,OSError,ET.ParseError) as e:p.exit(2,f'Conversion failed: {e}\n')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(scene,indent=2)+'\n')
    print(f'Converted {len(scene["bodies"])} bodies. Limitations: {scene["limitations"]}')
if __name__=='__main__':main()
