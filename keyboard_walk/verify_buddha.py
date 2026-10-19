#!/usr/bin/env python3
"""Run reproducible complete demos and check grasp, placement and camera invariants.

Example: .venv/bin/python keyboard_walk/verify_buddha.py --seeds 0 1 2 3 4 5 6 7 8 9
Artifacts go to /tmp/buddha_validation by default. Seed 9 also pauses in transit.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

import mujoco
import numpy as np

from buddha_task import BuddhaTask, angle_error, yaw_of


def worker(seed, directory):
    import g1_keyboard
    original_attach = BuddhaTask.attach
    original_transition = BuddhaTask.transition
    original_update = BuddhaTask.update
    report = {'seed':seed, 'states':[], 'grasp_checks':0, 'pause_checked':False}
    latest = []

    def attach(self):
        before = self.d.qpos[self.obj_q:self.obj_q+7].copy()
        attached = original_attach(self)
        if attached:
            np.testing.assert_array_equal(before,self.d.qpos[self.obj_q:self.obj_q+7])
            report['grasp_checks'] += 1
        return attached

    def transition(self,state):
        if state == 'retreat':
            assert not self.attached
            assert self.stable_since is not None and self.d.time-self.stable_since >= 1
            report['placed_position'] = self.d.xpos[self.body].tolist()
        if state == 'celebrate':
            error = abs(angle_error(self.face_heading,yaw_of(self.d.qpos[3:7])))
            assert error < .10
            report['camera_error_radians'] = error
        original_transition(self,state)
        report['states'].append({'state':state,'time':self.d.time})
        latest[:] = [self]
        if state in {'lift','carry','place','retreat','celebrate','done','failed'}:
            np.savez(directory/f'seed_{seed}_{state}.npz',qpos=self.d.qpos.copy())

    def update(self,target,camera):
        if seed == 9 and self.state == 'carry' and self.d.time-self.since > 3 and not hasattr(self,'validation_pause'):
            self.pause()
            self.validation_pause = self.d.time
            self.validation_obj = self.d.xpos[self.body].copy()
        if seed == 9 and self.paused and self.d.time-self.validation_pause > 2:
            assert self.attached
            assert np.linalg.norm(self.d.xpos[self.body]-self.validation_obj) < .08
            self.resume()
            report['pause_checked'] = True
        if self.state == 'celebrate' and self.d.time-self.since > 3:
            snapshot = directory/f'seed_{seed}_celebration.npz'
            if not snapshot.exists():
                np.savez(snapshot,qpos=self.d.qpos.copy())
        return original_update(self,target,camera)

    BuddhaTask.attach, BuddhaTask.transition, BuddhaTask.update = attach,transition,update
    sys.argv = ['g1_keyboard.py','--headless','--seed',str(seed),'--duration','180']
    try:
        g1_keyboard.main()
        assert latest and latest[0].success and not latest[0].attached
        assert report['grasp_checks'] == 1
        report['success'] = True
    except Exception as exc:
        report['success'] = False
        report['error'] = str(exc)
        raise
    finally:
        (directory/f'seed_{seed}.json').write_text(json.dumps(report,indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,nargs='+',default=list(range(10)))
    parser.add_argument('--jobs',type=int,default=3)
    parser.add_argument('--output',type=Path,default=Path('/tmp/buddha_validation'))
    parser.add_argument('--worker',type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.worker is not None:
        worker(args.worker,args.output)
        return
    def run(seed):
        with (args.output/f'seed_{seed}.log').open('w') as log:
            result = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(seed),
                                     '--output',str(args.output)],stdout=log,stderr=subprocess.STDOUT,
                                    env={**os.environ,'OPENBLAS_NUM_THREADS':'1'},timeout=300)
        print(f'Seed {seed}: '+('PASS' if result.returncode == 0 else 'FAIL'),flush=True)
        return result.returncode == 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run,args.seeds))
    reports = [json.loads((args.output/f'seed_{s}.json').read_text()) for s in args.seeds
               if (args.output/f'seed_{s}.json').exists()]
    (args.output/'results.json').write_text(json.dumps(reports,indent=2))
    if not all(results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
