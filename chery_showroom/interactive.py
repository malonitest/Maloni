"""One visitor, one controller, physically confirmed escort and return."""
import math
import numpy as np
from .arrival_script import CUSTOMER_START
from .sales import normalized,is_stop,is_yes,is_no,mentioned_car,car_entry
from .localization import message
from .layout import VEHICLE_SITES
from .shared_scene import world_object
from .navigation import Navigator

class CustomerNavigator(Navigator):
    """Static clearance plus an exact exclusion disc around the live robot."""
    def __init__(self,base,robot,start,radius=1.65):
        super().__init__(obstacles=base.obstacles,bounds=base.bounds,clearance=base.clearance)
        self.robot=np.asarray(robot)
        self.radius=min(radius,max(1.4,np.linalg.norm(np.asarray(start)-self.robot)-.005))
    def segment_free(self,start,end):
        a=np.asarray(start);b=np.asarray(end);d=b-a
        t=np.clip(np.dot(self.robot-a,d)/max(np.dot(d,d),1e-12),0,1)
        return np.linalg.norm(a+t*d-self.robot)>=self.radius-1e-8 and super().segment_free(start,end)

class InteractiveVisit:
    def __init__(self,app):
        self.app=app;self.actor=app.demo.actor;self.reset()
    def reset(self):
        self.active=False;self.stage='idle';self.actor_state='stopped';self.actor_path=[]
        self.events=[];self.reason='';self.triggered=False;self.part=0;self.resume_part=False
        self.pending_part=None;self.suspended_stage=None;self.started=0.;self.arrived_at=None
        self.min_separation=float('inf');self.auto_camera=True;self.car=None
        self.next_plan=0.;self.follow_blocked_since=None;self.reported=False;self.interventions=0
        self.physics_ms=0.;self.policy_ms=0.
        self.avoid_direction=None
        self.home_quiet_since=None
        self.exit_quiet_since=None
    def event(self,name):
        self.events.append(dict(event=name,time=round(self.app.sim.data.time-self.started,3)))
    def say(self,text):self.app.reply(self.app.visit.say(text))
    def say_key(self,key,**values):self.say(message(key,**values))
    def start(self):
        app=self.app
        if not app.ready_for_visit():self.say_key('visit.finish_first');return
        self.reset();app.new_visit();self.active=True;self.stage='arrival'
        self.started=app.sim.data.time;self.started_recoveries=app.route_recoveries
        self.actor.pose(CUSTOMER_START,0,False);self.welcome=np.array(world_object(app.sim.definition,'customer_reception')['position'][:2])
        self.move_customer('approach');self.say_key('visit.arrival');self.event('started')
    def cancel(self):
        self.actor_state='stopped';self.actor_path=[];self.app.stop();self.event('cancelled')
        self.stage='cancelled';self.finish_report('cancelled');self.active=False
    def finish_report(self,status):
        if not self.active or self.reported:return
        self.reported=True
        self.app.record_visit(dict(run_id=self.app.run_id,language=self.app.language,car=self.car,
            status=status,events=list(self.events),sim_seconds=round(self.app.sim.data.time-self.started,3),
            operator_interventions=self.interventions,automatic_recoveries=self.app.route_recoveries-self.started_recoveries,
            failure_code=self.app.failure_code,physics_ms=self.physics_ms,policy_ms=self.policy_ms,
            manual_stop_latency_ms=self.app.manual_stop_latency_ms,manual_settle_ms=self.app.manual_settle_ms,
            physics_realtime_factor=1000*(self.app.sim.data.time-self.started)/self.physics_ms if self.physics_ms else None,
            min_separation=None if not np.isfinite(self.min_separation) else self.min_separation))
    def pause(self,reason=None,actor_stop=True):
        if not self.active:return
        if self.stage!='paused':self.suspended_stage=self.stage;self.event('paused')
        self.stage='paused';self.pending_part=None;self.reason=reason or message('visit.pause')
        self.app.stop()
        if actor_stop:self.actor_state='stopped';self.actor_path=[]
        self.say(self.reason)
    def choose(self,car):
        self.car=car;self.app.selected=self.app.visit.selected=car
        self.stage='offer';self.say_key('visit.offer',car=car_entry(car)['display_model']);self.event('car_selected')
    def move_customer(self,target):
        if target=='stop':self.actor_state='stopped';self.actor_path=[];return
        if target=='follow':self.actor_state='following';self.actor_path=[];return
        if target=='exit':
            self.pending_part=None;self.app.stop();self.stage='leaving';self.actor_state='waiting_exit'
            self.actor_path=[];self.exit_quiet_since=None
            self.say_key('visit.leaving');self.event('leaving');return
        try:self.actor_path=self.app.navigator.route(self.actor.position,self.welcome)
        except ValueError:self.app.fail(message('failure.blocked'),'blocked');return
        self.actor_state='approaching'
    def escort(self):
        if self.car is None:self.say_key('visit.choose');return
        self.stage='escort';self.reason='';self.actor_state='following';self.actor_path=[];self.next_plan=0.
        self.app.commands.put(('interactive_escort',self.car,self.app.run_id));self.event('escort_requested')
    def continue_visit(self):
        app=self.app
        if self.stage=='paused':
            if app.failure_code in ('stability','policy_timeout','policy_error'):
                self.say_key('visit.reset_required');return
            stage=self.suspended_stage;app.error='';app.failure_code='';self.reason='';self.event('resumed')
            if stage=='escort':self.escort()
            elif stage=='returning':self.return_home()
            elif stage=='leaving':self.move_customer('exit')
            elif stage in ('presentation','questions','handoff'):
                self.stage='questions';self.present(repeat=True)
            else:
                self.stage=stage or 'choose';self.say_key('visit.resume')
                if self.stage=='arrival':self.move_customer('approach')
            return
        if self.stage in ('presentation','questions'):self.present(repeat=self.resume_part)
        else:self.say_key('visit.wait')
    def present(self,repeat=False,retry=False):
        app=self.app
        if self.car is None:return
        goal=app.sim.model.site(VEHICLE_SITES[self.car]).pos[:2]
        if (np.linalg.norm(app.sim.data.qpos[:2]-goal)>.18 or not app.facing_vehicle(self.car)
            or app.path or not 1.4<=np.linalg.norm(self.actor.position-app.sim.data.qpos[:2])<2.):return
        if np.linalg.norm(app.sim.data.qvel[:2])>.1 or abs(app.sim.snapshot()['yaw_rate'])>.1:
            self.pending_part=repeat;return
        self.pending_part=None
        if self.stage in ('presentation','questions') and not repeat:self.part=min(2,self.part+1)
        self.stage='presentation';self.actor_state='stopped';self.actor_path=[];self.resume_part=False
        app.phase='presentation';app.gesture_kind='present';app.gesture_until=app.sim.data.time+4 if self.part<2 else 0
        entry=car_entry(self.car)
        self.say_key(('visit.present','visit.appearance','visit.questions')[self.part],car=entry['display_model'],year=entry['model_year'])
        self.event('presentation_part:'+str(self.part))
    def return_home(self):
        self.stage='returning';self.actor_state='stopped';self.actor_path=[]
        self.actor.pose(self.actor.position,self.actor.heading,False,hidden=True)
        self.app.commands.put(('interactive_return',self.car or self.app.selected,self.app.run_id))
        self.say_key('visit.returning');self.event('returning')
    def chat(self,text):
        app=self.app;t=' '.join(normalized(text).strip().strip('.!').replace(',',' ').split())
        app.gesture_until=0;self.pending_part=None
        if is_stop(t):self.interventions+=1;self.pause();return
        if t in ('konec','ukoncit navstevu','ukonci navstevu','end visit','finish visit','goodbye','na shledanou'):
            self.move_customer('exit');return
        if t in ('pokracovat','pokracujte','pokracuj','dale','dalsi cast','continue','next','next section','next part'):
            self.continue_visit();return
        if self.stage=='paused':
            # Questions are allowed, but never resume a suspended trajectory.
            self.say(app.visit.respond(text,self.car or app.selected,app.sim.data.time)[0]);return
        if self.stage in ('choose','offer','declined'):
            car=mentioned_car(t)
            if car and not any(w in t.split() for w in ('ne','nechci','not','no')):
                self.choose(car);return
            if self.stage=='offer' and is_yes(t):self.escort();return
            if is_no(t) or t in ('nemam zajem','jen se rozhlizim','not interested','just looking'):
                self.stage='declined';self.say_key('visit.declined');self.event('declined');return
            self.say_key('visit.choose' if self.car is None else 'visit.offer',car=car_entry(self.car)['display_model'] if self.car else '')
            return
        if self.stage in ('leaving','returning'):self.say_key('visit.wait');return
        if 'shrnuti' in t or 'summary' in t:
            app.visit.cancel();self.stage='handoff';self.say(app.visit.summary());self.event('handoff');return
        if self.stage=='presentation':self.resume_part=True;self.stage='questions'
        app.visit.cancel();app.visit.stage='consultation'
        answer=app.visit.respond(text,self.car or app.selected,app.sim.data.time)[0]
        app.visit.cancel();self.say(answer);self.event('question')
    def handle(self,action,text,car=None):
        if action in ('interactive_start','start_visit'):self.start();return True
        if not self.active:return False
        if action=='end_visit':self.move_customer('exit')
        elif action=='customer':self.move_customer(text)
        elif action=='interactive_continue':self.continue_visit()
        elif action=='interactive_camera':self.auto_camera=text=='on'
        elif action=='chat':self.chat(text)
        elif action=='stop':self.interventions+=1;self.pause()
        elif action=='handoff':self.chat('summary')
        elif action=='select' and self.stage in ('choose','offer','declined'):self.choose(car)
        elif action in ('escort','present','navigate','reception','greet','manual','select','advice','quick','entertainment'):
            self.say_key('visit.wait')
        else:return False
        return True
    def plan_follow(self,robot):
        app=self.app;old=self.actor.position;nav=CustomerNavigator(app.navigator,robot,old)
        candidates=[robot+[-1.75,-.4]] if self.avoid_direction is None else [robot-1.85*self.avoid_direction]
        candidates.extend(robot+1.85*np.array([math.cos(a),math.sin(a)]) for a in np.linspace(0,2*math.pi,16,endpoint=False))
        choices=[]
        for radius in (1.65,1.45):
            nav=CustomerNavigator(app.navigator,robot,old,radius=radius)
            for point in candidates:
                if self.avoid_direction is not None and np.dot(point-robot,self.avoid_direction)>.8:continue
                if not nav.free(point):continue
                try:route=nav.route(old,point)
                except ValueError:continue
                length=sum(np.linalg.norm(np.array(b)-a) for a,b in zip([old,*route],route))
                choices.append((length+.25*np.linalg.norm(point-candidates[0]),route))
                if len(choices)>=3:break
            if choices:break
        if choices:
            self.actor_path=min(choices,key=lambda row:row[0])[1];self.follow_blocked_since=None
        elif self.follow_blocked_since is None:self.follow_blocked_since=app.sim.data.time
    def update(self):
        if not self.active:return
        app=self.app;robot=app.sim.data.qpos[:2].copy()
        if app.error and self.stage!='paused':self.pause(app.error)
        if self.stage=='leaving' and self.actor_state=='waiting_exit':
            state=app.sim.snapshot()
            if np.linalg.norm(app.sim.data.qvel[:2])<.1 and abs(state['yaw_rate'])<.1:
                if self.exit_quiet_since is None:self.exit_quiet_since=app.sim.data.time
            else:self.exit_quiet_since=None
            if self.exit_quiet_since is not None and app.sim.data.time-self.exit_quiet_since>=.25:
                self.actor_state='leaving'
        if self.stage=='leaving' and self.actor_state=='leaving' and not self.actor_path and np.linalg.norm(self.actor.position-CUSTOMER_START)>=.1:
            try:self.actor_path=CustomerNavigator(app.navigator,robot,self.actor.position,radius=1.45).route(self.actor.position,CUSTOMER_START)
            except ValueError:app.fail(message('failure.blocked'),'blocked')
        if self.stage in ('presentation','questions','handoff'):
            separation=np.linalg.norm(self.actor.position-robot)
            if separation<1.65:self.actor_state='following'
            elif self.actor_state=='following' and separation>=1.8:self.actor_state='stopped';self.actor_path=[]
        old=self.actor.position.copy()
        if self.actor_state=='following' and app.sim.data.time>=self.next_plan:
            if not self.actor_path or np.linalg.norm(np.array(self.actor_path[-1])-robot)>2.:
                self.plan_follow(robot)
            self.next_plan=app.sim.data.time+.4
        point=old.copy()
        if self.actor_path:
            delta=np.array(self.actor_path[0])-old;length=np.linalg.norm(delta)
            candidate=old+delta*min(1.,1.1*app.sim.control_dt/max(length,1e-9))
            distance=np.linalg.norm(candidate-robot)
            if (distance>=1.4 or distance>np.linalg.norm(old-robot)) and app.navigator.segment_free(old,candidate):
                point=candidate
                if length<=1.1*app.sim.control_dt+1e-9:self.actor_path.pop(0)
            else:self.actor_path=[]
        delta=point-old;facing=delta if np.linalg.norm(delta)>1e-6 else robot-point
        self.actor.pose(point,math.atan2(facing[1],facing[0]),np.linalg.norm(delta)>1e-6,hidden=self.stage=='returning')
        distance=float(np.linalg.norm(point-robot));self.min_separation=min(self.min_separation,distance)
        if self.stage=='arrival' and np.linalg.norm(point-self.welcome)<.1:
            self.stage='choose';self.triggered=True;self.say_key('visit.choose');self.event('welcome')
        if self.stage=='escort':
            if self.follow_blocked_since is not None and app.sim.data.time-self.follow_blocked_since>15:
                app.fail(message('failure.blocked'),'blocked')
            elif app.phase=='arrived' and app.destination==VEHICLE_SITES[self.car]:
                if self.arrived_at is None:self.arrived_at=app.sim.data.time-self.started;self.event('arrived')
                if distance<2. and self.pending_part is None:self.present()
        if self.pending_part is not None and self.stage!='paused':self.present(repeat=self.pending_part,retry=True)
        if self.actor_state=='leaving' and np.linalg.norm(point-CUSTOMER_START)<.1:self.return_home()
        if self.stage=='returning':
            if app.phase=='arrived' and app.at_reception():
                if self.home_quiet_since is None:self.home_quiet_since=app.sim.data.time
            else:self.home_quiet_since=None
        if self.stage=='returning' and self.home_quiet_since is not None and app.sim.data.time-self.home_quiet_since>=.5:
            self.stage='completed';self.event('completed');self.say_key('visit.ready');self.finish_report('completed');self.active=False
            app.clear_customer_data()
        if self.auto_camera:
            app.camera_view='entrance_view' if self.stage=='arrival' else ('vehicle_demo_view' if self.stage in ('presentation','questions','handoff') else 'showroom_overview')
    def guard(self,cmd):
        if not self.active:return cmd
        app=self.app
        if self.stage=='paused' or app.error:return np.zeros(3)
        if self.stage=='returning':return cmd
        robot=app.sim.data.qpos[:2];distance=np.linalg.norm(self.actor.position-robot)
        if self.stage=='escort' and distance>2.1:
            # Wait for the independently planned customer, without losing the route.
            app.last_progress=app.sim.data.time;return np.zeros(3)
        w,x,y,z=app.sim.data.qpos[3:7];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        r=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])
        end=robot+r@cmd[:2]*.6;segment=end-robot
        factor=np.clip(np.dot(self.actor.position-robot,segment)/max(np.dot(segment,segment),1e-12),0,1)
        if np.linalg.norm(self.actor.position-(robot+factor*segment))<(1.7 if np.linalg.norm(segment)>1e-8 else 1.4):
            if self.stage=='escort' and distance>=1.4 and np.linalg.norm(segment)>1e-8:
                self.avoid_direction=segment/np.linalg.norm(segment);self.actor_state='following'
                self.actor_path=[];self.next_plan=0.;app.last_progress=app.sim.data.time
                return np.zeros(3)
            self.pause(message('failure.customer_close'),actor_stop=False);return np.zeros(3)
        return cmd
    def snapshot(self):
        return dict(active=self.active,stage=self.stage,car=self.car,actor_state=self.actor_state,
            customer_position=self.actor.position.tolist(),reason=self.reason,presentation_part=self.part,
            auto_camera=self.auto_camera,elapsed=round(self.app.sim.data.time-self.started,3) if self.active else 0,
            manual_stop_latency_ms=self.app.manual_stop_latency_ms,manual_settle_ms=self.app.manual_settle_ms,
            physics_realtime_factor=1000*(self.app.sim.data.time-self.started)/self.physics_ms if self.physics_ms else None,
            min_separation=None if not np.isfinite(self.min_separation) else self.min_separation,
            arrived_at=self.arrived_at,events=list(self.events),available_choices=['yes','no'] if self.stage=='offer' else (['continue'] if self.stage in ('paused','presentation','questions') else []))
