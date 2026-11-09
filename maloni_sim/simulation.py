"""G1 controller adapter; observation ordering matches the original ONNX contract."""
from collections import deque
from pathlib import Path
import json
import os
import selectors
import subprocess
import time
import numpy as np
from .world import World, ROOT, array
from .import_mjcf import convert, rotation

CONFIG=ROOT/'keyboard_walk/policy_config.json'
POLICY=ROOT/'unitree_rl_lab/deploy/robots/g1_29dof/config/policy/velocity/v0/exported/policy.onnx'
SCENE=ROOT/'unitree_mujoco/unitree_robots/g1/scene_29dof.xml'
NAMES=[f'{s}_{p}' for s in ('left','right') for p in ('hip_pitch','hip_roll','hip_yaw','knee','ankle_pitch','ankle_roll')]
NAMES+=['waist_yaw','waist_roll','waist_pitch']
NAMES += [f'{s}_{p}' for s in ('left','right') for p in ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw')]

class Simulation:
    """Experimental ground-contact-only G1. This is not an accepted walking backend."""
    def __init__(self,scene=None,*,policy=True,contact_scope="ground-only",reset_config=None):
        self.process=None;self.selector=None;self.world=None
        try:
            self.cfg=json.loads(CONFIG.read_text())
            self.world=World(convert(SCENE,contact_scope) if scene is None else scene)
            self.ids=np.array(self.cfg['joint_ids_map'],dtype=int)
            imu=[s for s in self.world.scene.get('sensors',[]) if s.get('name')=='imu_quat']
            if not imu or imu[0].get('objname')!='imu':raise ValueError('Expected root IMU site')
            motors={a['name']:a['joint'] for a in self.world.scene['actuators']}
            bounds={a['name']:a['ctrlrange'] for a in self.world.scene['actuators']}
            self.motor_limits=np.array([bounds[name] for name in NAMES])
            self.joints=np.array([self.world.joint_names.index(motors[name]) for name in NAMES])
            self.control_dt=self.cfg['step_dt'];self.substeps=round(self.control_dt/self.world.dt)
            if self.substeps<1 or abs(self.substeps*self.world.dt-self.control_dt)>1e-10:
                raise ValueError('Physics timestep must divide the policy period')
            self.use_policy=policy;self.reset(reset_config)
        except Exception:self.close();raise

    def reset(self,config=None):
        self._close_policy();self.config=(config if config is not None else getattr(self,'config',{}));self.world.reset()
        q,v=self.world.state();q[7+self.joints[self.ids]]=self.cfg['default_joint_pos']
        noise=float(self.config.get('joint_noise',0))
        if not np.isfinite(noise) or noise<0:raise ValueError('Invalid reset noise')
        if noise:
            q[7:]+=np.random.default_rng(self.config.get('seed',0)).uniform(-noise,noise,self.world.nj)
            limits=[b['joint'].get('range',[-1e30,1e30]) for b in self.world.bodies if b.get('joint')]
            q[7:]=np.clip(q[7:],np.array(limits)[:,0],np.array(limits)[:,1])
        self.world.set_state(q,v)
        self.history=[deque(maxlen=5) for _ in range(6)];self.action=np.zeros(29)
        if self.use_policy:
            runner=ROOT/'keyboard_walk/policy_runner'
            if not runner.is_file() or not POLICY.is_file():raise RuntimeError('Missing ONNX runner or policy; run bash keyboard_walk/build_policy_runner.sh')
            self.process=subprocess.Popen([str(runner),str(POLICY)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,bufsize=0)
            os.set_blocking(self.process.stdin.fileno(),False);os.set_blocking(self.process.stdout.fileno(),False)
            self.selector=selectors.DefaultSelector();self.selector.register(self.process.stdout,selectors.EVENT_READ)

    def observation(self,command):
        command=array(command,(3,));q,v=self.world.state();r=rotation(q[3:7])
        # Source imu is at the free-root origin with identity local rotation.
        values=[r.T@v[3:6]*.2,r.T@np.array([0,0,-1]),command,
                q[7+self.joints[self.ids]]-self.cfg['default_joint_pos'],v[6+self.joints[self.ids]]*.05,self.action]
        for history,value in zip(self.history,values):
            for _ in range(5 if not history else 1):history.append(value.copy())
        return np.concatenate([np.concatenate(h) for h in self.history])

    def step(self,command):
        command=array(command,(3,));obs=self.observation(command);started=time.perf_counter()
        if self.use_policy:
            try:
                action=self._request_policy(obs)
                if action.shape!=(29,) or not np.isfinite(action).all():raise RuntimeError('Invalid ONNX action')
                self.action=action
            except Exception:self._close_policy();raise
        policy_ms=(time.perf_counter()-started)*1000
        return dict(self.step_action(self.action,command),policy_ms=policy_ms)

    def _request_policy(self,observation):
        timeout=float(self.config.get('policy_timeout',5))
        if not np.isfinite(timeout) or timeout<=0:raise ValueError('Invalid policy timeout')
        deadline=time.monotonic()+timeout
        payload=(' '.join(map(str,observation))+'\n').encode('ascii');sent=0
        with selectors.DefaultSelector() as writer:
            writer.register(self.process.stdin,selectors.EVENT_WRITE)
            while sent<len(payload):
                remaining=deadline-time.monotonic()
                if remaining<=0 or not writer.select(remaining):raise TimeoutError('ONNX policy input timed out')
                try:sent+=os.write(self.process.stdin.fileno(),payload[sent:])
                except BlockingIOError:continue
        response=bytearray()
        while b'\n' not in response:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not self.selector.select(remaining):raise TimeoutError('ONNX policy response timed out')
            try:chunk=os.read(self.process.stdout.fileno(),4096)
            except BlockingIOError:continue
            if not chunk:raise RuntimeError('ONNX policy exited')
            response.extend(chunk)
            if len(response)>65536:raise RuntimeError('Oversized ONNX response')
        line,extra=bytes(response).split(b'\n',1)
        if extra.strip():raise RuntimeError('Unexpected extra ONNX response')
        return np.fromstring(line.decode('ascii'),sep=' ')

    def step_action(self,action,command=(0,0,0)):
        self.action=array(action,(29,)).copy();command=array(command,(3,))
        target=np.empty(29);target[self.ids]=np.asarray(self.cfg['default_joint_pos'])+.25*self.action
        if callable(getattr(self,'pose_target',None)):target=array(self.pose_target(target.copy()),(29,))
        started=time.perf_counter()
        for _ in range(self.substeps):
            q,v=self.world.state();torques=np.zeros(self.world.nj)
            torques[self.joints]=np.clip(np.asarray(self.cfg['stiffness'])*(target-q[7+self.joints])-np.asarray(self.cfg['damping'])*v[6+self.joints],self.motor_limits[:,0],self.motor_limits[:,1])
            self.world.step(torques)
        return dict(self.snapshot(),command=command.tolist(),policy_command=command.tolist(),policy_ms=0.,
                    physics_ms=(time.perf_counter()-started)*1000,control_mode='raw',calibration_hash=None)

    def snapshot(self):
        q,v=self.world.state();r=rotation(q[3:7]);diagnostics=self.world.diagnostics()
        return dict(sim_time=diagnostics['sim_time'],position=q[:3].tolist(),orientation=q[3:7].tolist(),
            velocity=(r.T@v[:3]).tolist(),angular_velocity=(r.T@v[3:6]).tolist(),yaw_rate=float(v[5]),
            tilt=float(np.arccos(np.clip(r[2,2],-1,1))),fallen=bool(q[2]<.35),joint_names=NAMES,
            joint_positions=q[7+self.joints].tolist(),joint_velocities=v[6+self.joints].tolist(),
            backend='maloni-native',physics_scope=('convex-body-contacts' if 'body_contacts' in self.world.scene.get('requires',[]) else 'ground-only'),assisted=False,diagnostics=diagnostics)

    def _close_policy(self):
        if self.selector:self.selector.close();self.selector=None
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            for stream in (self.process.stdin,self.process.stdout):
                try:stream.close()
                except OSError:pass
            self.process=None
    def close(self):
        self._close_policy()
        if self.world:self.world.close();self.world=None
