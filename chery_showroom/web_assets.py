"""Explicit public graphics routes; no simulation state or credentials are served here."""
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote
from .layout import CARS
from .shared_scene import scene_definition,world_object,collision_boxes
from .library_models import MODELS

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'web' / 'dist'
ASSETS = ROOT / 'assets'


def layout_payload(definition=None):
    definition=scene_definition() if definition is None else definition
    vehicles=[]
    for key in CARS:
        obj=world_object(definition,key)
        vehicles.append(dict(id=key,name=MODELS[key][1],url='/graphics/'+MODELS[key][0]+'.glb',position=obj['position'],length=obj['size'][0],yaw=obj['yaw']))
    car=next(v for v in vehicles if v['id']=='tiggo8')
    return dict(car={'position':car['position'],'length':car['length']},vehicles=vehicles,scene=definition,
        collision_boxes=[dict(id=name,size=size,position=position,yaw=yaw) for name,size,position,yaw in collision_boxes(definition)])


def asset_response(url):
    """Return (status, bytes, MIME) or None for non-graphics routes."""
    path = unquote(url.split('?', 1)[0])
    if not (path.startswith('/web/') or path.startswith('/graphics/')):
        return None
    if '\\' in path or '\x00' in path or any(p in ('.', '..') for p in path.split('/')):
        return 404, b'Not found', 'text/plain'
    if path == '/graphics/layout.json':
        return 200,json.dumps(layout_payload()).encode(),'application/json'
    fixed = {'/graphics/chery.glb': ASSETS / 'library' / 'chery-tiggo.glb',
             '/graphics/studio.hdr': DIST / 'studio.hdr',
             '/graphics/daylight.hdr': DIST / 'daylight.hdr',
             '/graphics/staff/g1-reception.glb': DIST / 'models' / 'g1-reception.glb',
             '/graphics/staff/receptionist.glb': DIST / 'models' / 'receptionist.glb',
             '/graphics/signage-font.json': DIST / 'signage-font.json'}
    fixed.update({'/graphics/furniture/' + name + '.glb': DIST / 'models' / (name + '.glb')
                  for name in ('modern_arm_chair_01', 'potted_plant_02')})
    fixed.update({'/graphics/materials/' + name + '-' + role + '.png': DIST / 'materials' / (name + '-' + role + '.png')
                  for name in ('stone', 'wood', 'metal') for role in ('color', 'normal', 'roughness')})
    fixed.update({'/graphics/materials/' + name + '-' + role + '.jpg': DIST / 'materials' / (name + '-' + role + '.jpg')
                  for name in ('marble', 'walnut', 'limestone-floor', 'limestone-wall') for role in ('color', 'normal', 'roughness')})
    fixed.update({'/graphics/' + name + '.glb': ASSETS / 'library' / (name + '.glb') for name, _ in MODELS.values()})
    if path in fixed:
        target = fixed[path]
    elif path.startswith('/web/'):
        target = (DIST / (path[5:] or 'index.html')).resolve()
        if not target.is_relative_to(DIST.resolve()):
            return 404, b'Not found', 'text/plain'
    else:
        return 404, b'Not found', 'text/plain'
    try:
        data = target.read_bytes()
    except (OSError, ValueError):
        return 404, b'Graphics asset unavailable; rebuild frontend', 'text/plain'
    mime = {'.js': 'text/javascript', '.glb': 'model/gltf-binary', '.hdr': 'application/octet-stream'}.get(target.suffix)
    return 200, data, mime or mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
