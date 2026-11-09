"""Collision counterparts of the existing Three.js showroom; no visual redesign."""
import numpy as np
import copy
from functools import lru_cache
from .layout import CARS, WAYPOINTS
from maloni_sim.import_mjcf import convert
from maloni_sim.simulation import SCENE

from .shared_scene import scene_definition,world_object,waypoint,collision_boxes
RECEPTION=np.array(waypoint(scene_definition(),'reception')[:2])
BOXES=[(name.replace('_',' '),size,center) for name,size,center,yaw in collision_boxes(scene_definition())]

def robot_scene(definition=None):
    definition=scene_definition() if definition is None else definition
    scene=copy.deepcopy(_robot_model())
    reception=world_object(definition,'robot_reception');scene['position'][:2]=reception['position'][:2]
    yaw=reception['yaw'];scene['orientation']=[np.cos(yaw/2),0,0,np.sin(yaw/2)]
    scene['static_colliders']=[];scene['static_object_ids']=[]
    for name,size,center,yaw in collision_boxes(definition):
        half=np.asarray(size)/2;c=np.asarray(center);co,si=np.cos(yaw),np.sin(yaw)
        rotation=np.array([[co,-si,0],[si,co,0],[0,0,1]])
        points=[(c+rotation@(half*np.array([x,y,z]))).tolist() for x in [-1,1] for y in [-1,1] for z in [-1,1]]
        scene['static_colliders'].append(dict(points=points,radius=0,friction=1));scene['static_object_ids'].append(name)
    return scene

@lru_cache(maxsize=1)
def _robot_model():
    scene=convert(SCENE,'full');scene['name']='MALONI existing automotive gallery'
    scene['position'][:2]=RECEPTION.tolist();scene['orientation']=[2**-.5,0,0,-2**-.5]
    # Preserve all visual geometry. Convex collision proxies keep deterministic
    # directional extrema, including every axis bound, instead of 100k STL vertices.
    directions=[np.array([x,y,z],dtype=float) for x in [-1,0,1] for y in [-1,0,1] for z in [-1,0,1] if x or y or z]
    for i in range(96):
        z=1-2*(i+.5)/96;angle=i*np.pi*(3-np.sqrt(5));r=np.sqrt(1-z*z)
        directions.append(np.array([r*np.cos(angle),r*np.sin(angle),z]))
    directions=np.array(directions)
    for body in scene['bodies']:
        for collider in body['colliders']:
            points=np.asarray(collider.get('points',[]))
            if len(points)>len(directions):
                indices=np.argmax(np.einsum('ij,kj->ik',points,directions,optimize=False),axis=0)
                collider['points']=np.unique(points[indices],axis=0).tolist()
    scene['collision_approximation']='Convex proxies from 122 deterministic support directions; source axis bounds preserved; visuals unchanged'
    scene['limitations']=['Convex collision approximation of existing vehicle and furnishing geometry; demonstration, not real robot certification']
    return scene

def navigation(definition=None):
    from .navigation import Navigator
    definition=scene_definition() if definition is None else definition
    obstacles=[];nav=definition['navigation']
    for name,size,center,yaw in collision_boxes(definition):
        half=np.array(size)/2;c=np.array(center)
        co,si=abs(np.cos(yaw)),abs(np.sin(yaw));extent=np.array([co*half[0]+si*half[1],si*half[0]+co*half[1]])
        extra=0. if name=='staff_desk' else nav['extra_clearance']
        if c[2]+half[2]>.12:obstacles.append((c[:2]-extent-extra,c[:2]+extent+extra))
    return Navigator(obstacles=obstacles,bounds=nav['bounds'],clearance=nav['clearance'])
