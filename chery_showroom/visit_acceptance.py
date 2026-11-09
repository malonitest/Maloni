"""Complete bilingual native visits, serial reuse and standing acceptance; no cloud."""
import argparse,hashlib,json,multiprocessing,os,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import threading
from contextlib import contextmanager
from .controller import Showroom
from .stability import profile


def tick(app):
    app.last_client=time.monotonic();app.tick()
    if app.error or app.sim.snapshot()['fallen']:raise RuntimeError(app.failure_code+': '+app.error)
    if app.interactive.stage=='paused':raise RuntimeError('Unexpected pause: '+app.interactive.reason)

def wait(app,predicate,timeout=180):
    end=app.sim.data.time+timeout
    while not predicate():
        tick(app)
        if app.sim.data.time>end:raise TimeoutError(str(app.interactive.snapshot()))

def command(app,action,**values):
    app.command(dict(action=action,run_id=app.run_id,**values));tick(app)

@contextmanager
def connected_client(app):
    """Model the browser's independent state polling while A* is planning."""
    stop=threading.Event()
    def heartbeat():
        while not stop.wait(.1):app.last_client=time.monotonic()
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:yield
    finally:stop.set();thread.join(timeout=1)

def visit(app,car,language):
    with connected_client(app):return _visit(app,car,language)

def _visit(app,car,language):
    started=time.perf_counter();sim_start=app.sim.data.time;origin=app.sim.data.qpos[:2].copy()
    command(app,'set_language',language=language);wait(app,app.ready_for_visit,20)
    old=app.run_id;command(app,'start_visit')
    assert app.run_id!=old
    wait(app,lambda:app.interactive.stage=='choose',30)
    command(app,'select',car=car);assert not app.path
    command(app,'chat',text='ano' if language=='cs' else 'yes')
    wait(app,lambda:app.interactive.stage=='presentation',180)
    assert app.facing_vehicle(car)
    for _ in range(2):
        wait(app,lambda:not app.gesture_until,10)
        command(app,'interactive_continue');wait(app,lambda:app.interactive.pending_part is None,10)
    command(app,'chat',text='Kolik stojí toto auto?' if language=='cs' else 'How much does this car cost?')
    assert ('ověřen' in app.state['message'] if language=='cs' else 'verif' in app.state['message'])
    assert app.visit.topics
    command(app,'end_visit');wait(app,lambda:app.interactive.stage=='completed' and app.ready_for_visit(),180)
    assert app.ready_for_visit() and not any(app.visit.needs.values()) and not app.visit.topics
    row=dict(app.visit_reports[-1],passed=True,wall_seconds=time.perf_counter()-started,
        sim_seconds=app.sim.data.time-sim_start,final_position=app.sim.data.qpos[:2].tolist(),
        reception_distance=float(np.linalg.norm(app.sim.data.qpos[:2]-app.sim.model.site('reception').pos[:2])),
        policy_pid=app.sim.process.pid)
    return row

def trial(seed,car,language):
    app=None;start=time.perf_counter()
    try:
        app=Showroom(simulation_options=profile(seed));row=visit(app,car,language);row['seed']=seed
        return row
    except Exception as error:
        return dict(seed=seed,car=car,language=language,passed=False,error=type(error).__name__+': '+str(error),
            wall_seconds=time.perf_counter()-start,state=app.interactive.snapshot() if app else None,
            position=app.sim.data.qpos[:3].tolist() if app else None)
    finally:
        if app:app.close()

def standing(seed):
    app=Showroom(simulation_options=profile(seed));start=time.perf_counter();physics=policy=0.;max_tilt=0.;samples=0
    try:
        while app.sim.data.time<62:
            tick(app);max_tilt=max(max_tilt,app.sim.snapshot()['tilt'])
            if app.sim.data.time>=2:
                physics+=app.state['physics_ms'];policy+=app.state['policy_ms'];samples+=1
        return dict(seed=seed,passed=True,sim_seconds=60,wall_seconds=time.perf_counter()-start,
            physics_seconds=physics/1000,policy_seconds=policy/1000,
            physics_realtime_factor=60/(physics/1000),max_tilt=max_tilt,samples=samples)
    except Exception as error:return dict(seed=seed,passed=False,error=str(error))
    finally:app.close()

def serial():
    app=Showroom();rows=[]
    try:
        for index in range(10):
            row=visit(app,['tiggo4','tiggo7','tiggo8'][index%3],['cs','en'][index%2]);rows.append(row)
            print(json.dumps(dict(serial=index+1,passed=True)),flush=True)
        return dict(passed=len({r['policy_pid'] for r in rows})==1,visits=rows,
                    unique_policy_processes=len({r['policy_pid'] for r in rows}))
    except Exception as error:return dict(passed=False,visits=rows,error=type(error).__name__+': '+str(error),state=app.interactive.snapshot())
    finally:app.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--mode',choices=['matrix','standing','serial'],default='matrix')
    parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if not 1<=args.workers<=5:parser.error('workers must be between 1 and 5')
    digest=hashlib.sha256()
    for file in sorted(Path(__file__).parent.glob('*.py')):digest.update(file.read_bytes())
    for name in ['messages.json','shared_scene.json','native_velocity.json']:digest.update(Path(__file__).with_name(name).read_bytes())
    fingerprint=digest.hexdigest()
    result=dict(version=1,mode=args.mode,source_hash=fingerprint,status='running',rows=[])
    if args.resume and args.output.exists():
        result=json.loads(args.output.read_text())
        if result['source_hash']!=fingerprint or result['mode']!=args.mode:parser.error('Source or mode changed')
    def save():
        args.output.parent.mkdir(parents=True,exist_ok=True);tmp=args.output.with_suffix('.tmp')
        tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(args.output)
    if args.mode=='matrix':
        done={(r['seed'],r['car'],r['language']) for r in result['rows']}
        cases=[(s,c,l) for s in range(5) for c in ['tiggo4','tiggo7','tiggo8'] for l in ['cs','en'] if (s,c,l) not in done]
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            futures=[pool.submit(trial,*case) for case in cases]
            for future in as_completed(futures):
                row=future.result();result['rows'].append(row);save()
                print(json.dumps({k:row.get(k) for k in ['seed','car','language','passed','error']},ensure_ascii=False),flush=True)
    elif args.mode=='standing':
        result['rows']=[]
        for seed in range(5):result['rows'].append(standing(seed));save();print(json.dumps(result['rows'][-1]),flush=True)
    else:
        row=serial();result['rows']=[row];save()
    passed=bool(result['rows']) and all(r['passed'] for r in result['rows'])
    if args.mode=='matrix':passed=passed and len(result['rows'])==30
    if args.mode=='standing':passed=passed and all(r.get('physics_realtime_factor',0)>=1 for r in result['rows'])
    result['status']='passed' if passed else 'failed';save();return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
