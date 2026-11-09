"""Metre-based layout and compatibility names shared by MJCF and navigation."""
from .shared_scene import scene_definition,world_object,waypoint
_DEFINITION=scene_definition()
CARS={name:(*world_object(_DEFINITION,name)['position'][:2],world_object(_DEFINITION,name)['size'][0]) for name in ('tiggo4','tiggo7','tiggo8')}
WAYPOINTS={name:tuple(waypoint(_DEFINITION,name)[:2]) for name in _DEFINITION['waypoints']}
VEHICLE_SITES=dict(zip(CARS,('vehicle_1','vehicle_2','vehicle_3')))
STOPS={key:WAYPOINTS[site] for key,site in VEHICLE_SITES.items()}
STOPS['reception']=WAYPOINTS['reception']
CAMERAS=('showroom_overview','entrance_view','reception_view','vehicle_demo_view','detail_view','furniture_detail',
         'overview','customer','entrance','robot','hero_tiggo4','hero_tiggo7','hero_tiggo8','cinematic')
QUALITY={'interactive':dict(shadowsize=2048,offsamples=2),'presentation':dict(shadowsize=4096,offsamples=4)}
