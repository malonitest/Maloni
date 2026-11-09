"""Single source of placements and collision dimensions for Python and the gallery."""
import copy
import json
import math
from pathlib import Path

PATH=Path(__file__).with_name('shared_scene.json')

def world_object(scene,name):
    def resolve(key,trail):
        if key in trail:raise ValueError('Cyclic scene parent: '+key)
        obj=scene['objects'][key];position=list(obj['position']);yaw=float(obj.get('yaw',0))
        if obj.get('parent'):
            parent=resolve(obj['parent'],trail|{key});c,s=math.cos(parent['yaw']),math.sin(parent['yaw'])
            x,y,z=position;position=[parent['position'][0]+c*x-s*y,parent['position'][1]+s*x+c*y,parent['position'][2]+z];yaw+=parent['yaw']
        return dict(obj,position=position,yaw=yaw)
    return resolve(name,set())

def waypoint(scene,name):
    item=scene['waypoints'][name];p=list(item['position'])
    if item.get('parent'):
        parent=world_object(scene,item['parent']);c,s=math.cos(parent['yaw']),math.sin(parent['yaw']);x,y,z=p
        p=[parent['position'][0]+c*x-s*y,parent['position'][1]+s*x+c*y,parent['position'][2]+z]
    return p

def collision_boxes(scene):
    for name in scene['objects']:
        obj=world_object(scene,name);spec=obj.get('collision',True)
        if spec is False:continue
        spec={} if spec is True else spec
        size=list(obj['size']);yaw=obj['yaw'];c,s=math.cos(yaw),math.sin(yaw)
        x,y,z=spec.get('offset',[0,0,0]);p=obj['position'];center=[p[0]+c*x-s*y,p[1]+s*x+c*y,p[2]+z]
        if spec.get('floor_to_top'):
            top=center[2]+size[2]/2;size[2]=top;center[2]=top/2
        yield name,size,center,yaw+spec.get('yaw',0)

def validate(scene):
    if scene.get('version')!=1 or scene.get('units')!='metres' or scene.get('up_axis')!='z':raise ValueError('Unsupported showroom scene')
    nav=scene['navigation']
    if not math.isfinite(nav['return_clearance']) or nav['return_clearance']<nav['clearance']:raise ValueError('Invalid return corridor clearance')
    offset=nav['return_entry_offset']
    if len(offset)!=2 or not all(math.isfinite(v) for v in offset):raise ValueError('Invalid return entry offset')
    for name in scene['objects']:
        obj=world_object(scene,name)
        if len(obj['position'])!=3 or not all(math.isfinite(v) for v in [*obj['position'],obj['yaw']]):raise ValueError('Invalid object pose: '+name)
        if obj['kind']!='anchor' and (len(obj.get('size',[]))!=3 or not all(math.isfinite(v) and v>0 for v in obj['size'])):raise ValueError('Invalid object size: '+name)
    for name,size,position,yaw in collision_boxes(scene):
        if len(position)!=3 or not all(math.isfinite(v) for v in [*size,*position,yaw]) or min(size)<=0:raise ValueError('Invalid collider: '+name)
    for name in scene['waypoints']:
        if not all(math.isfinite(v) for v in waypoint(scene,name)):raise ValueError('Invalid waypoint: '+name)
    return scene

# One snapshot per process keeps HTTP layout and an already-loaded world consistent.
_SCENE=validate(json.loads(PATH.read_text()))
def scene_definition():return copy.deepcopy(_SCENE)
