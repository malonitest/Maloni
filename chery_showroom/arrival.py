"""Existing staged arrival, waiting for physically confirmed arrival before presenting."""
import json
import math
from pathlib import Path
import numpy as np
from .pose_math import matrix_quaternion, forward, camera_sync
from .customer_actor import CustomerActor

from .arrival_script import SCRIPT,DURATION,HOST_START,CUSTOMER_START,CUSTOMER_WELCOME


class ArrivalDemo:
    def __init__(self,app):
        self.app=app
        self.default_shadows=app.sim.model.light_castshadow.copy()
        self.actor=app.create_customer_actor() if hasattr(app,'create_customer_actor') else CustomerActor(app.sim.model,app.sim.data)
        self.reset()

    def reset(self):
        self.app.sim.model.light_castshadow[:]=self.default_shadows
        self.timeline_delay=0.;self.actual_elapsed=0.
        self.active=False;self.status='idle';self.started=0.;self.elapsed=0.
        self.events=[];self.triggered=False;self.travel_started=False
        self.presentation_requested=False;self.presentation_started=False
        self.arrived_at=None;self.min_separation=float('inf');self.cue=None
        self.actor.distance=0.;self.actor.pose(CUSTOMER_START,0,False,hidden=True)

    def record(self,event):
        self.events.append(dict(event=event,time=round(self.elapsed,3)))

    def start(self):
        app=self.app
        # Reset-time placement only. No qpos writes occur after this initialization.
        app.reset()
        app.sim.data.qpos[:2]=HOST_START
        direction=CUSTOMER_WELCOME-HOST_START;yaw=math.atan2(direction[1],direction[0])
        app.sim.data.qpos[3:7]=[math.cos(yaw/2),0,0,math.sin(yaw/2)]
        forward(app.sim)
        if not app.navigator.segment_free(HOST_START,app.sim.model.site('vehicle_3').pos[:2]):
            raise ValueError('Demo route lacks static clearance.')
        # Daylight is the shadow-casting key; all other lights remain as fill.
        app.sim.model.light_castshadow[:]=False
        app.sim.model.light_castshadow[app.sim.model.light('window_daylight').id]=True
        self.active=True;self.status='arrival';self.started=app.sim.data.time
        app.selected=app.visit.selected='tiggo8'
        app.visit.mode='tour';app.camera_view='showroom_overview'
        self.actor.pose(CUSTOMER_START,math.atan2(*(CUSTOMER_WELCOME-CUSTOMER_START)[::-1]),False)
        app.reply(app.visit.say('The customer arrival demonstration is ready.'))
        self.record('started')

    def cancel(self,status='stopped'):
        if self.active:
            self.record(status)
            self.active=False;self.status=status;self.cue=None

    def failed(self,message):
        self.cancel('failed')
        self.app.fail(message)

    def snapshot(self):
        return dict(name='customer_arrival',active=self.active,status=self.status,
                    elapsed=round(self.elapsed,3),sim_elapsed=round(self.actual_elapsed,3),timeline_delay=round(self.timeline_delay,3),remaining=max(0,round(DURATION-self.elapsed,3)),
                    customer_position=self.actor.position.tolist(),cue=self.cue,
                    triggered=self.triggered,arrived_at=self.arrived_at,
                    min_separation=None if not np.isfinite(self.min_separation) else self.min_separation,
                    events=list(self.events))

    def camera(self):
        if self.status=='idle':return
        t=self.elapsed
        if t<6:pos=(7.7,-5.2,2.15);target=(2.7,-2.2,1.05)
        elif t<12:pos=(7.6,-3.2,1.75);target=(4.,-1.2,1.05)
        elif t<34:
            robot=self.app.sim.data.qpos[:2]
            pos=(min(7.8,robot[0]+2.7),robot[1]-4.1,1.8)
            midpoint=(robot+self.actor.position)/2
            target=(*midpoint,1.0)
        elif t<41 or t>=46:pos=(3.,-3.6,1.8);target=(5.8,2.3,1.1)
        else:pos=(3.35,1.45,.72);target=(4.6,3.1,.65)
        forward=np.array(target)-pos;forward/=np.linalg.norm(forward)
        right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right)
        up=np.cross(right,forward);quaternion=np.empty(4)
        quaternion[:]=matrix_quaternion(np.column_stack((right,up,-forward)))
        cam=self.app.sim.model.camera('cinematic').id
        self.app.sim.model.cam_pos[cam]=pos;self.app.sim.model.cam_quat[cam]=quaternion
        camera_sync(self.app.sim.model,self.app.sim.data)

    def update(self):
        if not self.active:return
        app=self.app;self.actual_elapsed=round(app.sim.data.time-self.started,8)
        self.elapsed=self.actual_elapsed-self.timeline_delay
        # Keep the existing words, cue durations, images and camera sequence. A
        # new physics backend may take longer to align: never narrate an arrival
        # before navigation confirms it, and never fake a robot pose to meet a cue.
        ready=(app.phase=='arrived' and np.linalg.norm(app.sim.data.qvel[:2])<.14 and abs(app.sim.snapshot()['yaw_rate'])<.14)
        if self.travel_started and not self.presentation_requested and not ready and self.elapsed>33.9:
            self.timeline_delay+=self.elapsed-33.9;self.elapsed=33.9
        if app.error:
            self.cancel('failed');return
        t=self.elapsed
        robot=app.sim.data.qpos[:2].copy()
        old=self.actor.position.copy()
        if t<6:
            alpha=min(1,t/5.5)
            point=CUSTOMER_START+(CUSTOMER_WELCOME-CUSTOMER_START)*alpha
        elif t<12:
            point=CUSTOMER_WELCOME.copy()
        else:
            desired=robot+[-1.5,-.4]
            delta=desired-old;length=np.linalg.norm(delta)
            point=old+delta*min(1,1.1*.02/max(length,1e-9))
            if np.linalg.norm(point-robot)<1.3 or not app.navigator.segment_free(old,point):point=old
        delta=point-old
        facing=delta if np.linalg.norm(delta)>1e-6 else robot-point
        self.actor.pose(point,math.atan2(facing[1],facing[0]),np.linalg.norm(delta)>1e-6)
        separation=float(np.linalg.norm(point-robot));self.min_separation=min(self.min_separation,separation)
        if separation<1.2:
            self.failed('Demo stopped: insufficient customer separation.');return
        if t>=6 and not self.triggered:
            if separation>2.1:
                self.failed('The customer did not reach the welcome area.');return
            self.triggered=True;self.status='welcome';self.record('customer_entered_zone')
            app.commands.put(('demo_greet','tiggo8',app.run_id))
        if t>=12 and not self.travel_started:
            self.travel_started=True;self.status='escort';self.record('escort_requested')
            app.commands.put(('demo_escort','tiggo8',app.run_id))
        if self.travel_started and self.arrived_at is None and app.phase=='arrived' and app.destination=='vehicle_3':
            self.arrived_at=t;self.record('arrived')
        if t>=33.96 and not self.presentation_requested:
            if (self.arrived_at is None or self.arrived_at>34) and t>=34:
                self.failed('I could not complete the move in time. Stopping; we can continue here.');return
            if self.arrived_at is not None:
                self.presentation_requested=True;app.commands.put(('demo_present','tiggo8',app.run_id))
        if self.presentation_requested and not self.presentation_started:
            if app.gesture_until and app.phase=='presentation':
                self.presentation_started=True;app.visit.presentation=None
                self.status='presentation';self.record('presentation_started')
            elif t>34.2:
                self.failed('The presentation cannot safely start after stopping.');return
        if t>=DURATION:
            app.stop();self.active=False;self.status='completed';self.cue=None
            self.elapsed=DURATION;self.record('completed')
            return
        cue=next((c for c in SCRIPT['cues'] if c['start']<=t<c['end']),None)
        # Never announce a presentation before the local controller confirms it.
        if cue and cue['id'].startswith('presentation') and not self.presentation_started:cue=None
        if cue and self.cue!=cue['id']:
            self.cue=cue['id'];self.record('cue:'+self.cue)
            app.reply(app.visit.say(cue['en']))
        elif cue and app.message!=cue['en']:
            app.reply(app.visit.say(cue['en']))
        elif cue is None:self.cue=None
        app.camera_view='cinematic'
