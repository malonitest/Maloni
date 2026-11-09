"""Independent planar differential-drive dynamics; estimated parameters, not hardware validation.

No G1 scene, policy, actuator mapping or learned walking controller is used.
Flat-floor non-slip constraints and static circular-footprint contacts are assumed.
"""
import copy
import json
import math
import time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from .robot_types import Model
from .shared_scene import scene_definition, validate, world_object, collision_boxes

class Simulation:
    robot_model='maloni120'
    nonholonomic=True
    def __init__(self,*,definition=None,seed=0,joint_noise=0.,friction_scale=1.,start_offset=(0.,0.),yaw_offset=0.,command_scale=1.):
        values=np.array([joint_noise,friction_scale,*start_offset,yaw_offset,command_scale],dtype=float)
        if values.shape!=(6,) or not np.isfinite(values).all() or joint_noise<0 or not .1<=friction_scale<=3 or not .1<=command_scale<=2:raise ValueError('Invalid simulation test profile')
        self.parameters=json.loads(Path(__file__).with_name('robots').joinpath('maloni120.json').read_text())
        self.definition=validate(copy.deepcopy(scene_definition() if definition is None else definition))
        self.model=Model(self.definition);self.model.opt.timestep=self.parameters['physics_dt']
        self.control_dt=self.parameters['control_dt'];self.config={};self.command_scale=command_scale
        self.friction=self.parameters['friction']*friction_scale
        self.start_offset=np.asarray(start_offset);self.yaw_offset=yaw_offset
        self.seed=seed;self.joint_noise=joint_noise
        self.obstacles=collision_boxes(self.definition)
        self.world=SimpleNamespace(profile=self.profile)
        self.reset()
    def reset(self,config=None):
        self.config=dict(config or {});pose=world_object(self.definition,'robot_reception')
        self.xy=np.array(pose['position'][:2],dtype=float)+self.start_offset;self.yaw=pose['yaw']+self.yaw_offset
        self.speed=0.;self.omega=0.;self.wheel_angles=np.zeros(2);self.wheel_speeds=np.zeros(2);self.torques=np.zeros(2)
        self.joints=np.zeros(8);self.joint_velocity=np.zeros(8);self.joint_target=np.zeros(8)
        if self.joint_noise:self.joints=np.clip(np.random.default_rng(self.seed).uniform(-self.joint_noise,self.joint_noise,8),*np.array(self.parameters['joint_limits']).T)
        self.data=SimpleNamespace(time=0.,qpos=np.zeros(15),qvel=np.zeros(14));self.contact_count=0;self.emergency_stopped=False;self.physics_ms=0.
        self._sync()
    def _sync(self):
        self.data.qpos[:3]=[*self.xy,.6];self.data.qpos[3:7]=[math.cos(self.yaw/2),0,0,math.sin(self.yaw/2)]
        self.data.qpos[7:]=self.joints
        self.data.qvel[:6]=[self.speed*math.cos(self.yaw),self.speed*math.sin(self.yaw),0,0,0,self.omega]
        self.data.qvel[6:]=self.joint_velocity
    def forward(self):
        # Compatibility with the showroom's explicit reset-time scene placement.
        q=np.asarray(self.data.qpos)
        if q.shape!=(15,) or not np.isfinite(q).all():raise ValueError('Invalid robot state')
        self.xy=q[:2].copy();w,x,y,z=q[3:7]
        self.yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));self._sync()
    def emergency_stop(self):self.emergency_stopped=True;self.joint_target=self.joints.copy()
    def gesture(self,kind,elapsed,remaining):
        self.joint_target[:]=0
        if not self.emergency_stopped and remaining>0:
            blend=min(1.,max(0.,elapsed),remaining)
            self.joint_target[5]=-.6*blend;self.joint_target[6]=-.3*blend
            self.joint_target[7]=( .65+.15*math.sin(elapsed*5) if kind=='greet' else .8)*blend
            self.joint_target[0]=.12*math.sin(elapsed*2)*blend
            self.joint_target[1]=.08*math.sin(elapsed*3)*blend
            if kind!='greet':self.joint_target[2]=-.3*blend;self.joint_target[4]=.4*blend
    def _contact(self,xy):
        radius=self.parameters['footprint_radius']
        for name,size,center,yaw in self.obstacles:
            if center[2]+size[2]/2<=.025 or center[2]-size[2]/2>=self.parameters['height']:continue
            co,si=math.cos(yaw),math.sin(yaw);d=xy-np.array(center[:2]);local=np.array([co*d[0]+si*d[1],-si*d[0]+co*d[1]])
            distance=np.maximum(np.abs(local)-np.array(size[:2])/2,0)
            if np.dot(distance,distance)<radius**2:return name
        bounds=np.asarray(self.definition['navigation']['bounds'])
        if np.any(xy-radius<bounds[0]) or np.any(xy+radius>bounds[1]):return 'world-boundary'
        return None
    def step(self,command):
        requested=np.asarray(command,dtype=float)
        if requested.shape!=(3,) or not np.isfinite(requested).all():raise ValueError('Expected three finite velocities')
        started=time.perf_counter();p=self.parameters;h=p['physics_dt'];r=p['wheel_radius'];track=p['track']
        vx=float(np.clip(requested[0]*self.command_scale,-p['max_speed'],p['max_speed']))
        wz=float(np.clip(requested[2]*self.command_scale,-p['max_yaw_rate'],p['max_yaw_rate']))
        if self.emergency_stopped:vx=wz=0.
        target=np.clip(np.array([vx-wz*track/2,vx+wz*track/2])/r,-p['wheel_speed_limit'],p['wheel_speed_limit'])
        self.contact_count=0
        for _ in range(round(self.control_dt/h)):
            # Closed-loop motor torque, limited by actuator output and available traction.
            self.torques=np.clip(2.5*(target-self.wheel_speeds),-p['motor_torque_limit'],p['motor_torque_limit'])
            force_limit=self.friction*p['mass']*9.81/2
            forces=np.clip(self.torques/r,-force_limit,force_limit)
            mass=p['mass']+2*p['wheel_inertia']/r**2
            inertia=p['yaw_inertia']+p['wheel_inertia']*track**2/(2*r**2)
            self.speed+=h*(forces.sum()-p['rolling_drag']*self.speed)/mass
            self.omega+=h*((forces[1]-forces[0])*track/2-p['yaw_drag']*self.omega)/inertia
            yaw=self.yaw+self.omega*h;mid=(self.yaw+yaw)/2
            candidate=self.xy+self.speed*h*np.array([math.cos(mid),math.sin(mid)])
            if self._contact(candidate):self.speed=0.;self.contact_count+=1
            else:self.xy=candidate
            self.yaw=math.atan2(math.sin(yaw),math.cos(yaw))
            self.wheel_speeds=np.array([self.speed-self.omega*track/2,self.speed+self.omega*track/2])/r
            self.wheel_angles+=h*self.wheel_speeds
            acceleration=np.clip(35*(self.joint_target-self.joints)-10*self.joint_velocity,-4.,4.)
            self.joint_velocity=np.clip(self.joint_velocity+h*acceleration,-.9,.9)
            proposed=self.joints+h*self.joint_velocity;limits=np.array(p['joint_limits'])
            self.joints=np.clip(proposed,limits[:,0],limits[:,1]);self.joint_velocity[proposed!=self.joints]=0
            self.data.time+=h
        self._sync();self.physics_ms=(time.perf_counter()-started)*1000
        return dict(self.snapshot(),command=requested.tolist(),policy_command=[vx,0.,wz],policy_ms=0.,physics_ms=self.physics_ms)
    def snapshot(self):
        return dict(sim_time=self.data.time,position=self.data.qpos[:3].tolist(),orientation=self.data.qpos[3:7].tolist(),velocity=[self.speed,0.,0.],angular_velocity=[0.,0.,self.omega],yaw_rate=self.omega,tilt=0.,fallen=False,joint_names=self.parameters['joint_names'],joint_positions=self.joints.tolist(),joint_velocities=self.joint_velocity.tolist(),physics_ms=self.physics_ms,policy_ms=0.,backend='maloni120-planar',physics_scope='planar-differential-drive',assisted=False,diagnostics=dict(wheel_angles=self.wheel_angles.tolist(),wheel_speeds=self.wheel_speeds.tolist(),motor_torques=self.torques.tolist(),contacts=self.contact_count,emergency_stopped=self.emergency_stopped,parameters_status=self.parameters['status'],constraints='flat-floor, no-slip, no tipping model'))
    def transforms(self):return {'pelvis':self.data.qpos[:7].tolist()}
    def profile(self):return dict(backend='maloni120-planar',parameters=self.parameters,policy=False)
    def close(self):pass
