"""Measured acceptance of the existing showroom, not the unrelated simulator roadmap."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from chery_showroom.runtime import Showroom
from chery_showroom.layout import VEHICLE_SITES

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=dict(backend='maloni-native',passed=False,scenarios=[],scope='Existing automotive gallery; no redesign')
    app=Showroom()
    def save():args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    try:
        for car in VEHICLE_SITES:
            app.reset()
            for action in ['escort','reception']:
                app.command(dict(action=action,car=car));start=app.sim.data.time;wall=time.perf_counter()
                while app.sim.data.time-start<120:
                    app.last_client=time.monotonic();app.tick()
                    if app.error or app.phase=='arrived':break
                goal=app.sim.model.site(VEHICLE_SITES[car] if action=='escort' else 'reception').pos[:2]
                distance=float(np.linalg.norm(app.sim.data.qpos[:2]-goal))
                passed=not app.error and app.phase=='arrived' and distance<.18 and (action!='escort' or app.facing_vehicle(car))
                row=dict(car=car,action=action,passed=bool(passed),phase=app.phase,error=app.error,distance=distance,
                    sim_seconds=app.sim.data.time-start,wall_seconds=time.perf_counter()-wall,position=app.sim.data.qpos[:2].tolist())
                result['scenarios'].append(row);save();print(row,flush=True)
                if not passed:return 1
        app.demo.start();wall=time.perf_counter()
        while app.sim.data.time<120:
            app.last_client=time.monotonic();app.tick()
            if app.error or app.demo.status in ('failed','completed'):break
        passed=app.demo.status=='completed' and not app.error
        result['scenarios'].append(dict(scenario='customer_arrival',passed=passed,sim_seconds=app.sim.data.time,
            wall_seconds=time.perf_counter()-wall,demo=app.demo.snapshot(),error=app.error))
        result['passed']=passed
        root=Path(__file__).resolve().parents[2]
        result['source_hashes']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'chery_showroom/controller.py',root/'chery_showroom/native_simulation.py',root/'chery_showroom/native_scene.py',root/'chery_showroom/native_velocity.json',root/'chery_showroom/navigation.py',root/'chery_showroom/interactive.py',root/'chery_showroom/arrival.py',root/'chery_showroom/http_server.py',root/'maloni_sim/native/engine.cpp']}
        save();print('All native showroom routes and arrival:',passed,flush=True);return 0 if passed else 1
    finally:app.close()
if __name__=='__main__':raise SystemExit(main())
