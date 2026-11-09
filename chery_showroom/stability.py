"""Seeded robustness trials of the actual showroom physics and recovery controls."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from .runtime import Showroom
from .layout import VEHICLE_SITES

FRICTION=(.9,.95,1.,1.05,1.1)
SPEED=(.9,1.,1.1,1.,.95)
def profile(seed):
    rng=np.random.default_rng(seed)
    return dict(seed=seed,joint_noise=.001,friction_scale=FRICTION[seed%5],command_scale=SPEED[seed%5],
                start_offset=rng.uniform(-.005,.005,2).tolist(),yaw_offset=float(rng.uniform(-.005,.005)))

def trial(seed,car,*,timeout=120.,interrupt=False):
    options=profile(seed);app=None;wall=time.perf_counter();falls=0;interventions=0;max_tilt=max_penetration=max_residual=0.;started=False;stopped=False;resumed=False
    samples=0;error='';success=False;distance=None
    try:
        app=Showroom(simulation_options=options)
        end=app.sim.data.time+timeout
        while app.sim.data.time<end:
            app.last_client=time.monotonic();app.tick();samples+=1
            state=app.sim.snapshot();max_tilt=max(max_tilt,state['tilt'])
            diag=state['diagnostics'];max_penetration=max(max_penetration,diag['max_penetration']);max_residual=max(max_residual,diag['normal_residual'])
            if state['fallen'] or state['tilt']>.8:falls+=1;error=app.error or 'Lost stability';break
            if app.error:error=app.error;break
            if not started and state['sim_time']>=1:
                app.command(dict(action='escort',car=car));started=True
            if interrupt and started and not stopped and state['sim_time']>=4:
                app.command(dict(action='stop',car=car));stopped=True;interventions+=1
            if interrupt and stopped and not resumed and state['sim_time']>=5:
                if app.phase!='stopped' or app.path or app.gesture_until:error='Stop did not clear activity';break
                app.command(dict(action='escort',car=car));resumed=True
            if started and app.phase=='arrived':
                goal=app.sim.model.site(VEHICLE_SITES[car]).pos[:2];distance=float(np.linalg.norm(app.sim.data.qpos[:2]-goal))
                success=distance<.18 and app.facing_vehicle(car);break
        if not success and not error:error='Arrival deadline exceeded' if distance is None else 'Arrival outside tolerance'
        return dict(seed=seed,car=car,profile=options,interrupted=interrupt,passed=bool(success and not error),
            falls=falls,operator_interventions=interventions,error=error,sim_seconds=app.sim.data.time,
            wall_seconds=time.perf_counter()-wall,max_tilt_rad=max_tilt,max_penetration_m=max_penetration,
            max_normal_residual=max_residual,final_distance_m=distance,samples=samples,automatic_recoveries=app.route_recoveries,final_position=app.sim.data.qpos[:3].tolist())
    except Exception as exc:
        return dict(seed=seed,car=car,profile=options,interrupted=interrupt,passed=False,falls=falls,
                    operator_interventions=interventions,error=f'{type(exc).__name__}: {exc}',wall_seconds=time.perf_counter()-wall)
    finally:
        if app:app.close()

def summarize(rows):
    count=len(rows);passed=sum(r['passed'] for r in rows)
    return dict(trials=count,passed=passed,failed=count-passed,success_rate=passed/count if count else None,
        falls=sum(r['falls'] for r in rows),operator_interventions=sum(r['operator_interventions'] for r in rows),automatic_recoveries=sum(r.get('automatic_recoveries',0) for r in rows))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seeds',nargs='+',type=int,default=list(range(5)));p.add_argument('--cars',nargs='+',choices=list(VEHICLE_SITES),default=list(VEHICLE_SITES))
    p.add_argument('--timeout',type=float,default=120);p.add_argument('--resume',action='store_true');args=p.parse_args()
    if not math.isfinite(args.timeout) or args.timeout<=0:p.error('timeout must be positive and finite')
    config=dict(seeds=args.seeds,cars=args.cars,timeout=args.timeout)
    source=Path(__file__).resolve().parent
    digest=hashlib.sha256()
    for name in ['stability.py','controller.py','native_simulation.py','native_scene.py','native_velocity.json','shared_scene.json','navigation.py']:
        digest.update(name.encode());digest.update((source/name).read_bytes())
    run_hash=digest.hexdigest()
    result=dict(version=1,backend='maloni-native',configuration=config,source_hash=run_hash,status='running',trials=[])
    if args.resume and args.output.exists():
        result=json.loads(args.output.read_text())
        if result.get('configuration')!=config or result.get('source_hash')!=run_hash:p.error('Cannot resume results from different source code or settings')
    def save():
        result['summary']=summarize(result['trials']);args.output.parent.mkdir(parents=True,exist_ok=True)
        temporary=args.output.with_suffix('.tmp');temporary.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');temporary.replace(args.output)
    done={(r['seed'],r['car']) for r in result['trials']}
    try:
        for seed in args.seeds:
            for index,car in enumerate(args.cars):
                if (seed,car) in done:continue
                row=trial(seed,car,timeout=args.timeout,interrupt=(seed+index)%2==1)
                result['trials'].append(row);save();print(json.dumps({k:row[k] for k in ['seed','car','passed','falls','error']}),flush=True)
        result['status']='passed' if all(r['passed'] for r in result['trials']) else 'failed';save()
        return 0 if result['status']=='passed' else 1
    except KeyboardInterrupt:result['status']='interrupted';save();return 130
if __name__=='__main__':raise SystemExit(main())
