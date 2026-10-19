#!/usr/bin/env python3
"""Instrument a complete headless Buddha task without modifying its controller.

Times use perf_counter_ns (wall time). Policy RPC covers write/flush/readline,
not Python observation serialization or output parsing. No GPU/viewer benchmark.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

import mujoco
import numpy as np

import g1_keyboard
from buddha_task import BuddhaTask

ROOT = Path(__file__).resolve().parent.parent


def summary(values):
    if not values:
        return {'count':0}
    a = np.asarray(values)/1e6
    return {'count':len(a),'mean_ms':float(a.mean()),'p50_ms':float(np.percentile(a,50)),
            'p95_ms':float(np.percentile(a,95)),'p99_ms':float(np.percentile(a,99)),
            'max_ms':float(a.max()),'over_20ms':int(np.sum(a>20))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    values = {name:[] for name in ['cycle_interval','task_update','policy_rpc','mj_step']}
    phase_values = {}
    cycle_start = None
    first_cycle = None
    latest = None
    raw_events = []
    popen = g1_keyboard.subprocess.Popen
    update = BuddhaTask.update
    step = mujoco.mj_step
    transition = BuddhaTask.transition

    class Writer:
        def __init__(self,stream,owner): self.stream,self.owner=stream,owner
        def write(self,text):
            self.owner.request_start=time.perf_counter_ns()
            return self.stream.write(text)
        def __getattr__(self,name): return getattr(self.stream,name)

    class Reader:
        def __init__(self,stream,owner): self.stream,self.owner=stream,owner
        def readline(self):
            line=self.stream.readline()
            values['policy_rpc'].append(time.perf_counter_ns()-self.owner.request_start)
            return line
        def __getattr__(self,name): return getattr(self.stream,name)

    class Process:
        def __init__(self,*a,**kw):
            self.process=popen(*a,**kw)
            self.stdin=Writer(self.process.stdin,self)
            self.stdout=Reader(self.process.stdout,self)
        def __getattr__(self,name): return getattr(self.process,name)

    def timed_update(self,*a,**kw):
        nonlocal cycle_start,first_cycle,latest
        now=time.perf_counter_ns()
        if first_cycle is None: first_cycle=now
        if cycle_start is not None: values['cycle_interval'].append(now-cycle_start)
        cycle_start=now
        latest=self
        phase=self.state
        try:
            return update(self,*a,**kw)
        finally:
            duration=time.perf_counter_ns()-now
            values['task_update'].append(duration)
            phase_values.setdefault(phase,[]).append(duration)

    def timed_step(*a,**kw):
        now=time.perf_counter_ns()
        try: return step(*a,**kw)
        finally: values['mj_step'].append(time.perf_counter_ns()-now)

    def recorded_transition(self,state):
        raw_events.append({'state':state,'simulated_s':float(self.d.time)})
        return transition(self,state)

    g1_keyboard.subprocess.Popen=Process
    BuddhaTask.update=timed_update
    BuddhaTask.transition=recorded_transition
    mujoco.mj_step=timed_step
    sys.argv=['g1_keyboard.py','--headless','--task','buddha','--seed',str(args.seed),'--duration','180']
    started=time.perf_counter_ns()
    error=None
    load_start=os.getloadavg()
    try:
        g1_keyboard.main()
    except Exception as exc:
        error=str(exc)
        raise
    finally:
        ended=time.perf_counter_ns()
        g1_keyboard.subprocess.Popen=popen
        BuddhaTask.update=update
        BuddhaTask.transition=transition
        mujoco.mj_step=step
        total=(ended-started)/1e9
        sim=float(latest.d.time) if latest is not None else 0
        files=['keyboard_walk/g1_keyboard.py','keyboard_walk/buddha_task.py',
               'keyboard_walk/policy_runner','keyboard_walk/policy_config.json',
               'unitree_mujoco/unitree_robots/g1/scene_lab_task.xml',
               'unitree_mujoco/unitree_robots/g1/g1_29dof_task.xml',
               'unitree_rl_lab/deploy/robots/g1_29dof/config/policy/velocity/v0/exported/policy.onnx']
        result={'seed':args.seed,'success':bool(latest and latest.success), 'error':error,
                'environment':{'python':platform.python_version(),'mujoco':mujoco.__version__,
                               'numpy':np.__version__,'platform':platform.platform(),
                               'openblas_num_threads':os.environ.get('OPENBLAS_NUM_THREADS'),
                               'cpu_count':os.cpu_count(),'load_average_start':load_start,
                               'load_average_end':os.getloadavg()},
                'simulated_s':sim,'wall_total_s':total,
                'initialization_to_first_cycle_s':(first_cycle-started)/1e9 if first_cycle else None,
                'simulation_seconds_per_wall_second':sim/total,
                'metrics':{k:summary(v) for k,v in values.items()},
                'policy_rpc_excluding_first':summary(values['policy_rpc'][1:]),
                'first_policy_rpc_ms':values['policy_rpc'][0]/1e6 if values['policy_rpc'] else None,
                'task_update_by_state':{k:summary(v) for k,v in phase_values.items()},
                'events':raw_events,
                'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(f'Performance: {args.output}',flush=True)
        # Restore references for callers that run the benchmark in-process.
        g1_keyboard.subprocess.Popen=popen
        BuddhaTask.update=update
        BuddhaTask.transition=transition
        mujoco.mj_step=step


if __name__=='__main__':
    main()
