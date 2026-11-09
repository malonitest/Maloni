"""Shared showroom interface, independent of either robot physics implementation."""
from types import SimpleNamespace
import numpy as np
from .layout import CAMERAS
from .shared_scene import waypoint

class Model:
    native=True
    def __init__(self,definition):
        self.sites={name:SimpleNamespace(pos=np.array(waypoint(definition,name))) for name in definition['waypoints']}
        self.cam_pos=np.zeros((len(CAMERAS),3));self.cam_quat=np.tile([1.,0,0,0],(len(CAMERAS),1))
        self.light_castshadow=np.array([True]);self.opt=SimpleNamespace(timestep=.002)
    def site(self,name):return self.sites[name]
    def camera(self,name):return SimpleNamespace(id=CAMERAS.index(name))
    def light(self,name):
        if name!='window_daylight':raise KeyError(name)
        return SimpleNamespace(id=0)

class Customer:
    def __init__(self):self.position=np.array([0.,-4.85]);self.heading=0.;self.distance=0.;self.hidden=True;self.moving=False
    def pose(self,position,heading,moving,hidden=False):
        position=np.asarray(position,dtype=float)
        self.distance+=float(np.linalg.norm(position-self.position));self.position=position.copy()
        self.heading=float(heading);self.moving=bool(moving);self.hidden=hidden
    def snapshot(self):return dict(position=self.position.tolist(),heading=self.heading,moving=self.moving,hidden=self.hidden)

