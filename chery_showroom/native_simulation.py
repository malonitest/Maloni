"""Native physics adapter for the existing showroom controller."""
from types import SimpleNamespace
from pathlib import Path
import math
import copy
import numpy as np
from maloni_sim.simulation import Simulation as NativeSimulation
from .layout import WAYPOINTS,CAMERAS
from .native_scene import robot_scene,RECEPTION
from .shared_scene import scene_definition,world_object,waypoint,validate
from benchmark_lab.velocity import VelocityController

from .robot_types import Model,Customer

class Simulation(NativeSimulation):
    def __init__(self,*,definition=None,seed=0,joint_noise=0.,friction_scale=1.,start_offset=(0.,0.),yaw_offset=0.,command_scale=1.):
        numbers=np.asarray([joint_noise,friction_scale,*start_offset,yaw_offset,command_scale],dtype=float)
        if numbers.shape!=(6,) or not np.isfinite(numbers).all() or joint_noise<0 or not .1<=friction_scale<=3 or not .1<=command_scale<=2:raise ValueError('Invalid simulation test profile')
        self.reset_options={'seed':int(seed),'joint_noise':float(joint_noise)};self.command_scale=float(command_scale)
        self.definition=validate(copy.deepcopy(scene_definition() if definition is None else definition))
        scene=robot_scene(self.definition);scene['position'][:2]=(np.asarray(scene['position'][:2])+start_offset).tolist()
        from .pose_math import multiply
        scene['orientation']=multiply([np.cos(yaw_offset/2),0,0,np.sin(yaw_offset/2)],scene['orientation']).tolist()
        for body in [*scene['bodies'],{'colliders':scene['static_colliders']}]:
            for collider in body['colliders']:collider['friction']*=friction_scale
        self.model=Model(self.definition);self.data=SimpleNamespace(time=0.)
        super().__init__(scene=scene,policy=True,contact_scope='full')
        self.neutral_poses=[self.world.pose(i).tolist() for i in range(len(self.world.bodies))]
    def _sync(self):
        self.data.qpos,self.data.qvel=self.world.state();self.data.time=self.world.diagnostics()['sim_time']
    def reset(self,config=None):
        config=dict(config if config is not None else getattr(self,'config',{}));config.update(self.reset_options)
        super().reset(config);self._sync();self._turning_mode=False;self.velocity_controller=VelocityController(Path(__file__).with_name('native_velocity.json')) if self.config.get('control')=='velocity' else None
    def forward(self):self.world.set_state(self.data.qpos,self.data.qvel)
    def step(self,command):
        self.forward();original=np.asarray(command,dtype=float);requested=original*self.command_scale
        policy_command=requested
        if self.velocity_controller is not None:
            state=self.snapshot()
            turning=bool(np.linalg.norm(requested[:2])<.04 and abs(requested[2])>.03)
            cfg=self.velocity_controller.cfg
            if turning!=getattr(self,'_turning_mode',False):self.velocity_controller.integral[2]=0
            self._turning_mode=turning
            cfg['ki'][2]=.1 if turning else .02;cfg['integral_limit'][2]=.25 if turning else .025
            cfg['lower'][2]=-1.5 if turning else -.8;cfg['upper'][2]=.85 if turning else .6
            policy_command=self.velocity_controller.update(requested,[*state['velocity'][:2],state['yaw_rate']],self.control_dt)
        result=super().step(policy_command);self._sync();result['command']=original.tolist();result['policy_command']=policy_command.tolist();return result
    def transforms(self):
        return {name:self.world.pose(i).tolist() for i,name in enumerate(self.world.names)}
