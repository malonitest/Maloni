"""Existing showroom visit controller running on MALONI native physics."""
import math,queue,threading,time,uuid,json
from pathlib import Path
import numpy as np
from .robot_types import Customer
from .native_scene import navigation,RECEPTION
from .layout import STOPS,WAYPOINTS,VEHICLE_SITES,CAMERAS,CARS
from .pose_math import multiply
from .shared_scene import world_object
from .sales import CATALOG,Visit
from .arrival import ArrivalDemo
from .interactive import InteractiveVisit
from .cinematic import update as update_cinematic
from benchmark_lab.velocity import KEY_COMMANDS
from .localization import localize,message,message_key,LANGUAGES
from .navigation import Navigator

class Showroom:
    def __init__(self,quality="interactive",*,simulation_options=None,language='en',visit_log=None,robot_model='g1'):
        if language not in LANGUAGES:raise ValueError('Unsupported language')
        self.language=language;self.visit_log=Path(visit_log) if visit_log else None;self.visit_reports=[];self.failure_code=''
        if robot_model not in ('g1','maloni120'):raise ValueError('Unknown robot model')
        self.robot_model=robot_model
        if robot_model=='maloni120':
            from .maloni120_simulation import Simulation as RobotSimulation
        else:
            from .native_simulation import Simulation as RobotSimulation
        self.sim=RobotSimulation(**(simulation_options or {}))
        self.navigator=navigation(self.sim.definition)
        self.return_navigator=Navigator(obstacles=self.navigator.obstacles,bounds=self.navigator.bounds,clearance=self.sim.definition['navigation']['return_clearance'])
        self.demo=ArrivalDemo(self)
        self.interactive=InteractiveVisit(self)
        self.frame=None;self.camera_view='robot';self.camera_enabled=False;self.commands=queue.Queue();self.lock=threading.Lock();self.last_client=time.monotonic();self.selected='tiggo4';self.message='Welcome to the MALONI Robotics automotive showroom. Independent simulation demonstration.';self.revision=0;self.reset()
    def create_customer_actor(self):return Customer()
    def reset(self):
        if self.interactive.active:self.interactive.finish_report('reset')
        self.sim.reset({'control':'velocity'});self.sim.forward()
        self.demo.reset()
        self.interactive.reset()
        self.visit=Visit();self.selected=self.visit.selected;self.message=self.visit.message;self.gesture_kind='present';self.manual=np.zeros(3);self.destination='reception';self.frame=None;self.run_id=uuid.uuid4().hex;self.path=[];self.phase='greeting';self.gesture_until=0;self.error='';self.route_recoveries=0;self.last_progress=self.sim.data.time;self.best=1e9
        self.failure_code='';self.sim.config['policy_timeout']=.25;self._policy_failed=False
        self._manual_expired=False;self.manual_seq=-1;self.manual_deadline=0.;self.manual_stop_latency_ms=None;self.manual_stopped_at=None
        self.manual_settle_ms=None;self.manual_last_received=0.;self.last_requested=np.zeros(3)
        self.heading_best=1e9
        self.return_leg=None
        self.return_entry_target=None
    def at_reception(self):
        s=self.sim.snapshot()
        return bool(np.linalg.norm(self.sim.data.qpos[:2]-self.sim.model.site('reception').pos[:2])<.18 and np.linalg.norm(self.sim.data.qvel[:2])<.1 and abs(s['yaw_rate'])<.1 and s['tilt']<.25 and not s['fallen'])
    def ready_for_visit(self):return not self.interactive.active and not self.error and not self.path and not np.any(self.manual) and self.at_reception()
    def clear_customer_data(self):
        self.visit=Visit();self.visit.message=self.message
    def new_visit(self):
        self.stop();self.demo.reset();self.clear_customer_data();self.run_id=uuid.uuid4().hex
        self.return_leg=None;self.return_entry_target=None;self.manual_seq=-1;self._manual_expired=False
        self.failure_code='';self.visit.serial+=1
        while not self.commands.empty():
            try:self.commands.get_nowait()
            except queue.Empty:break
    def record_visit(self,row):
        self.visit_reports.append(row);self.visit_reports=self.visit_reports[-50:]
        if self.visit_log:
            self.visit_log.parent.mkdir(parents=True,exist_ok=True)
            with self.visit_log.open('a') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    def stop(self):
        if np.any(self.manual):self.manual_stopped_at=time.monotonic()
        self.path=[];self.manual[:]=0;self.manual_deadline=0.;self.gesture_until=0;self.phase='stopped'
    def accept_manual(self,v):
        if v.get('run_id')!=self.run_id:raise ValueError('Stale manual generation')
        seq=v.get('sequence')
        if type(seq) is not int or seq<0:raise ValueError('Expected nonnegative sequence')
        try:velocity=np.array([v['vx'],v['vy'],v['yaw_rate']],dtype=float)
        except (KeyError,TypeError,ValueError,OverflowError):raise ValueError('Expected finite robot-local velocities')
        if velocity.shape!=(3,) or any(type(v[k]) not in (int,float) for k in ('vx','vy','yaw_rate')) or not np.isfinite(velocity).all():raise ValueError('Expected finite robot-local velocities')
        if self.interactive.active or self.demo.active or self.error:raise ValueError('End the visit and clear faults before manual control')
        begin=v.get('begin',False)
        if type(begin) is not bool:raise ValueError('Expected boolean begin')
        if np.any(velocity) and (self._manual_expired or (self.phase=='manual' and time.monotonic()>=self.manual_deadline)) and not begin:raise ValueError('Manual lease expired; release and press again')
        with self.lock:
            if seq<=self.manual_seq:raise ValueError('Stale manual sequence')
            self.manual_seq=seq
        # Timestamp ingress: queued packets never acquire a fresh lease when consumed.
        self.commands.put(('manual_control',self.selected,(np.clip(velocity,[-.3,-.2,-.2],[.5,.2,.2]),time.monotonic(),begin),self.run_id))
    def reply(self,result):
        self.message,self.selected,action=result
        return action
    def fail(self,detail,code=None):
        if code is None:
            code='disconnected' if 'connection' in detail.lower() else ('stability' if 'stability' in detail.lower() else 'blocked')
        if self.interactive.active and self.failure_code!=code:self.interactive.event('failure:'+code)
        self.failure_code=code
        detail=message('failure.'+code)
        self.stop()
        if self.error==detail and self.visit.stage=='paused':return
        if self.interactive.active:self.interactive.pause(detail)
        self.error=detail
        self.reply(self.visit.interrupted(detail+' We can continue our conversation here.'))
    def facing_vehicle(self,car):
        delta=np.array(world_object(self.sim.definition,car)['position'][:2])-self.sim.data.qpos[:2]
        w,x,y,z=self.sim.data.qpos[3:7]
        yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        heading=math.atan2(delta[1],delta[0])
        return abs(math.atan2(math.sin(heading-yaw),math.cos(heading-yaw)))<.25
    def on_key(self,key):
        if key==32:self.commands.put(('stop',self.selected,''))
        elif key==ord('R'):self.commands.put(('reset',self.selected,''))
        elif key in KEY_COMMANDS:self.commands.put(('manual',self.selected,str(key)))
        elif ord('1')<=key<=ord('5'):
            self.commands.put(('view',self.selected,CAMERAS[key-ord('1')]))
    def command(self,v):
        a=v.get('action');car=v.get('car',self.selected)
        if a=='manual_control':return self.accept_manual(v)
        if car not in STOPS or car=='reception':raise ValueError('Unknown car.')
        if a not in ('select','escort','present','stop','reset','chat','reception','camera','view','navigate','advice','quick','entertainment','handoff','greet','scenario','interactive_start','customer','interactive_continue','interactive_camera','set_language','start_visit','end_visit','emergency_stop'):raise ValueError('Unknown action.')
        if a=='set_language' and v.get('language',v.get('text')) not in LANGUAGES:raise ValueError('Unsupported language')
        if a=='scenario' and v.get('scenario','customer_arrival')!='customer_arrival':raise ValueError('Unknown scenario.')
        if a=='navigate' and v.get('target') not in WAYPOINTS:raise ValueError('Unknown navigation target.')
        accepted_run=self.run_id
        if v.get('run_id',accepted_run)!=accepted_run:raise ValueError('The scene was reset; refresh the panel state.')
        if a=='customer' and v.get('text') not in ('approach','follow','stop','exit'):raise ValueError('Unknown customer target.')
        if a=='interactive_camera' and v.get('text') not in ('on','off'):raise ValueError('Unknown camera mode.')
        self.commands.put((a,car,str(v.get('language',v.get('text','')) if a=='set_language' else (v.get('target') if a=='navigate' else v.get('text','')))[:2000],accepted_run))
    def tick(self):
        while not self.commands.empty():
            queued=self.commands.get_nowait()
            if len(queued)==4:
                a,car,text,run=queued
                if run!=self.run_id:continue
            else:a,car,text=queued
            if a=='manual_control':
                velocity,received,begin=text
                if self.interactive.active or self.demo.active or self.error or time.monotonic()-received>=.3:continue
                if self._manual_expired and np.any(velocity) and not begin:continue
                if begin:self._manual_expired=False
                self.stop();self.visit.cancel();self.manual[:]=velocity
                self.manual_last_received=received;self.manual_deadline=received+.25
                if np.any(velocity):self.manual_stop_latency_ms=None;self.manual_settle_ms=None;self.manual_stopped_at=None
                self.phase='manual' if np.any(velocity) else 'stopped'
                if not np.any(velocity):self.manual_stopped_at=time.monotonic()
                continue
            if a=='set_language':
                if self.interactive.active:self.reply(self.visit.say(message('visit.language_locked')))
                else:self.language=text
                continue
            if a=='scenario':self.demo.start();continue
            returning=False
            if a in ('interactive_escort','interactive_return'):
                returning=a=='interactive_return'
                if not self.interactive.active or self.interactive.stage!=('returning' if returning else 'escort') or text!=self.run_id:continue
                a='reception' if returning else 'escort';interactive_internal=True
            else:interactive_internal=False
            if not interactive_internal and self.interactive.handle(a,text,car):continue
            internal=a in ('demo_escort','demo_present','demo_greet')
            if internal:
                if not self.demo.active or text!=self.run_id:continue
                a=a.removeprefix('demo_')
            if self.demo.active and not internal and a not in ('camera','view'):
                self.demo.cancel()
            if a=='manual':
                if self.interactive.active or self.demo.active or self.error:continue
                self.stop();self.visit.cancel();self.manual[:]=KEY_COMMANDS[int(text)];self._manual_expired=False;self.manual_deadline=time.monotonic()+.3;self.manual_last_received=time.monotonic();self.phase='manual';continue
            if a=='camera':self.camera_enabled=text=='on';continue
            if a=='view':
                if text in CAMERAS:self.camera_view=text;self.frame=None
                continue
            if a=='chat':
                # Any utterance cancels an active gesture/presentation before processing.
                self.gesture_until=0
                if self.phase=='presentation':self.phase='consultation'
                from .robot_dialogue import respond as robot_reply
                identity=robot_reply(text,self.robot_model,self.language)
                if identity:
                    self.reply(self.visit.say(identity));continue
                previous=self.selected
                a=self.reply(self.visit.respond(text,self.selected,self.sim.data.time));car=self.selected
                if previous!=self.selected or self.visit.mode=='entertainment' or self.visit.stage=='handoff':self.stop()
                if a is None:continue
            if a=='emergency_stop':
                self.stop()
                if hasattr(self.sim,'emergency_stop'):self.sim.emergency_stop()
                self.fail('Emergency stop','emergency_stop');continue
            if a=='reset':self.reset();continue
            if a=='stop':
                self.stop()
                if self.visit.mode=='idle':pass
                else:self.reply(self.visit.interrupted('Stopping movement, gestures and the current activity.'))
                continue
            if a=='select':
                self.stop();self.reply(self.visit.select(car));continue
            if a in ('advice','quick','entertainment'):
                self.stop();self.visit.selected=car
                self.reply(self.visit.start({'advice':'advice','quick':'quick','entertainment':'entertainment'}[a],self.sim.data.time));continue
            if a=='handoff':
                self.stop();self.reply(self.visit.respond('salesperson summary',self.selected,self.sim.data.time));continue
            if a=='greet':
                if self.path or np.any(self.manual) or self.error or np.linalg.norm(self.sim.data.qvel[:2])>.15 or abs(self.sim.snapshot()['yaw_rate'])>.15:
                    self.message='A greeting gesture is available only after a safe stop.'
                else:
                    self.visit.cancel();self.gesture_kind='greet';self.gesture_until=self.sim.data.time+4
                    self.phase='greeting_gesture';self.reply(self.visit.say('Hello from MALONI Robotics!'))
                continue
            if a in ('escort','reception','navigate'):
                self.stop();self.visit.activity=None;self.visit.presentation=None;self.selected=car
                self.destination=text if a=='navigate' else ('reception' if a=='reception' else VEHICLE_SITES[car])
                if self.destination in VEHICLE_SITES.values():
                    self.selected=next(k for k,v in VEHICLE_SITES.items() if v==self.destination)
                self.visit.selected=self.selected
                if self.error:
                    self.message='Please reset the simulation first.';continue
                target=self.sim.model.site(self.destination).pos[:2]
                if interactive_internal and returning:
                    if self.return_leg is None:
                        near_home=np.linalg.norm(self.sim.data.qpos[:2]-target)<.4
                        self.return_leg='home' if near_home else 'entry'
                        self.return_entry_target=self.sim.model.site(VEHICLE_SITES[car]).pos[:2]+np.asarray(self.sim.definition['navigation']['return_entry_offset'])
                    target=(self.return_entry_target if self.return_leg=='entry' else self.sim.model.site('reception_approach' if self.return_leg=='approach' else 'reception').pos[:2])
                else:self.return_leg=None
                planner=self.return_navigator if self.return_leg=='approach' else self.navigator
                try:
                    self.path=planner.route(self.sim.data.qpos[:2],target,allow_recovery=True)
                    if planner.last_recovery:self.route_recoveries+=1
                except ValueError:
                    self.fail('I could not plan a safe route. Stopping.');continue
                self.error='';self.phase='escort';self.message=('Please follow me.' if self.demo.active else 'Please follow me. I will stop in front of the car for a clear view.') if self.destination in VEHICLE_SITES.values() else 'I will move to the selected location.';self.visit.message=self.message;self.visit.serial+=1;self.last_progress=self.sim.data.time;self.best=1e9
                self.heading_best=1e9
            if a=='present':
                if self.error:self.message='Please reset the simulation first.'
                elif np.linalg.norm(self.sim.data.qpos[:2]-self.sim.model.site(VEHICLE_SITES[car]).pos[:2])>.55:self.message='Please complete the escort to this car first.'
                elif self.path or np.any(self.manual) or np.linalg.norm(self.sim.data.qvel[:2])>.15 or abs(self.sim.snapshot()['yaw_rate'])>.15:self.message='The presentation can start once we have stopped.'
                elif not self.facing_vehicle(car):self.message='Please complete the escort and turn towards the car first.'
                else:self.selected=car;self.visit.selected=car;self.phase='presentation';self.gesture_kind='present';self.gesture_until=self.sim.data.time+4;self.reply(self.visit.present(self.sim.data.time))
        self.demo.update()
        self.interactive.update()
        if self.message!=self.visit.message:self.reply(self.visit.say(self.message))
        s=self.sim.snapshot()
        if self.phase=='manual' and time.monotonic()>=self.manual_deadline:
            self._manual_expired=True
            self.manual_stop_latency_ms=(time.monotonic()-self.manual_last_received)*1000
            self.stop()
        if self.manual_stopped_at is not None and self.manual_settle_ms is None and np.linalg.norm(s['velocity'][:2])<.1 and abs(s['yaw_rate'])<.1:
            self.manual_settle_ms=(time.monotonic()-self.manual_stopped_at)*1000
        cmd=self.manual.copy() if self.phase=='manual' else np.zeros(3)
        if s['fallen'] or s['tilt']>.8:self.fail('The robot lost stability. Reset the scene to continue.')
        if time.monotonic()-self.last_client>2 and (self.path or self.gesture_until or np.any(self.manual) or self.visit.activity or self.visit.presentation or self.demo.active or self.interactive.active):self.fail('Dashboard connection lost.')
        if self.phase=='manual':
            w,x,y,z=s['orientation'];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
            c,sn=math.cos(yaw),math.sin(yaw);delta=np.array([[c,-sn],[sn,c]])@cmd[:2]
            if self.error or not self.navigator.segment_free(self.sim.data.qpos[:2],self.sim.data.qpos[:2]+delta):
                self.fail('Movement was stopped before an obstacle.');cmd[:]=0
        if self.phase=='stopped':cmd[:]=0
        if self.path and not self.error and self.phase!='aligning':
            delta=np.array(self.path[0])-self.sim.data.qpos[:2];dist=np.linalg.norm(delta)
            path_nav=self.return_navigator if self.return_leg=='approach' else self.navigator
            can_skip=len(self.path)==1 or path_nav.segment_free(self.sim.data.qpos[:2],self.path[1])
            tolerance=.1 if len(self.path)==1 and self.return_leg in ('entry','approach') else (.12 if len(self.path)>1 else .25)
            if dist<tolerance and can_skip:
                if len(self.path)==1 and self.return_leg in ('entry','approach'):
                    self.return_leg='approach' if self.return_leg=='entry' else 'home'
                    target=self.sim.model.site('reception_approach' if self.return_leg=='approach' else 'reception').pos[:2]
                    planner=self.return_navigator if self.return_leg=='approach' else self.navigator
                    try:self.path=planner.route(self.sim.data.qpos[:2],target,allow_recovery=True)
                    except ValueError:self.fail(message('failure.blocked'),'blocked')
                elif len(self.path)==1:self.phase='aligning'
                else:self.path.pop(0)
                self.best=1e9;self.last_progress=self.sim.data.time
                self.heading_best=1e9
            else:
                w,x,y,z=s['orientation'];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));heading=math.atan2(delta[1],delta[0]);err=math.atan2(math.sin(heading-yaw),math.cos(heading-yaw))
                cmd[2]=np.clip(err,-.35,.35)
                if abs(err)<.3:cmd[0]=min(.22,dist*.5)
                if dist<self.best-.04:self.best=dist;self.last_progress=self.sim.data.time
                if abs(err)<self.heading_best-.1:
                    self.heading_best=abs(err);self.last_progress=self.sim.data.time
                if self.sim.data.time-self.last_progress>35:self.fail('The route is blocked or no progress is being made. Stopping.');cmd[:]=0
        if self.phase=='aligning':
            if self.destination in VEHICLE_SITES.values():
                key=next(k for k,v in VEHICLE_SITES.items() if v==self.destination);look=np.array(world_object(self.sim.definition,key)['position'][:2])
            else:look=np.array({'reception':(-2.2,-4.05),'entrance':(0,0),'waiting_area':(6.5,-3.7),'reception_approach':tuple(world_object(self.sim.definition,'customer_reception')['position'][:2])}[self.destination])
            delta=look-self.sim.data.qpos[:2];w,x,y,z=s['orientation']
            yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));heading=math.atan2(delta[1],delta[0]);err=math.atan2(math.sin(heading-yaw),math.cos(heading-yaw))
            cmd[2]=0. if abs(err)<.05 else np.clip(2*err,-.35,.35)
            error=np.array(self.path[-1])-self.sim.data.qpos[:2]
            c,sn=math.cos(yaw),math.sin(yaw)
            local=np.array([[c,sn],[-sn,c]])@error
            if getattr(self.sim,'nonholonomic',False):
                distance=float(np.linalg.norm(error))
                if distance>=.14:
                    bearing=math.atan2(error[1],error[0])-yaw
                    bearing=math.atan2(math.sin(bearing),math.cos(bearing))
                    cmd[2]=np.clip(2*bearing,-.5,.5)
                    cmd[0]=min(.13,.6*distance) if abs(bearing)<.3 else 0.
                else:cmd[0]=0.
                cmd[1]=0.
            else:cmd[:2]=np.clip(.6*local,-.13,.13)
            remaining=np.linalg.norm(error)+abs(err)*.3
            if remaining<self.best-.02:self.best=remaining;self.last_progress=self.sim.data.time
            if self.sim.data.time-self.last_progress>35:
                self.fail('Could not complete the turn in place. Stopping.');cmd[:]=0
            if abs(err)<.07 and abs(s['yaw_rate'])<.1 and np.linalg.norm(error)<.18:
                self.path=[];self.phase='arrived';cmd[:]=0
                actual=next((k for k,v in VEHICLE_SITES.items() if v==self.destination),None)
                self.reply(self.visit.arrived(actual))
        event=self.visit.advance(self.sim.data.time)
        if event:
            if self.reply(event)=='stop':self.stop();cmd[:]=0
        cmd=self.interactive.guard(cmd)
        # Arm gesture is a bounded actuator target while the walking policy balances.
        self.last_requested=cmd.copy()
        if self.robot_model=='maloni120':
            remaining=max(0.,self.gesture_until-self.sim.data.time)
            self.sim.gesture(self.gesture_kind,4-remaining,remaining)
        else:self.sim.pose_target=self.pose_target
        try:
            result=self.sim.snapshot() if self._policy_failed else self.sim.step(cmd)
        except (TimeoutError,RuntimeError,OSError):
            import sys
            code='policy_timeout' if isinstance(sys.exception(),TimeoutError) else 'policy_error'
            self._policy_failed=True;self.fail(message('failure.'+code),code);result=self.sim.snapshot()
        result.setdefault('physics_ms',0.);result.setdefault('policy_ms',0.)
        if self.interactive.active:
            self.interactive.physics_ms+=result['physics_ms'];self.interactive.policy_ms+=result['policy_ms']
        if self.gesture_until:
            if self.sim.data.time>=self.gesture_until:
                self.gesture_until=0
                if self.phase!='stopped':self.phase='consultation'
        camera=self.sim.model.camera('robot').id
        self.sim.model.cam_pos[camera]=self.sim.data.qpos[:3]+[0,0,.485]
        w,x,y,z=self.sim.data.qpos[3:7]
        yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        base=np.array([.5,.5,-.5,-.5])
        self.sim.model.cam_quat[camera]=multiply(np.array([math.cos(yaw/2),0,0,math.sin(yaw/2)]),base)
        self.sim.forward()
        update_cinematic(self.sim.model,self.sim.data,self.sim.data.time)
        self.demo.camera()
        if self.error and self.demo.active:self.demo.cancel('failed')
        self.revision+=1
        state=dict(run_id=self.run_id,position=result['position'],phase=self.phase,selected=self.selected,message=self.message,error=self.error,revision=self.revision,camera_view=self.camera_view,destination=self.destination,waypoints={name:self.sim.model.site(name).pos[:2].tolist() for name in WAYPOINTS},sim_time=result['sim_time'],physics_ms=result['physics_ms'],policy_ms=result['policy_ms'],gesture=bool(self.gesture_until),conversation=self.visit.snapshot(),message_id=self.visit.serial,catalog=CATALOG,demo=self.demo.snapshot(),interactive=self.interactive.snapshot(),backend=result.get('backend','maloni-native'),route_recoveries=self.route_recoveries,orientation=result['orientation'],robot_transforms=self.sim.transforms(),customer=self.demo.actor.snapshot(),camera_pose={'position':self.sim.model.cam_pos[self.sim.model.camera(self.camera_view).id].tolist(),'quaternion':self.sim.model.cam_quat[self.sim.model.camera(self.camera_view).id].tolist()},physics_scope=result.get('physics_scope','native-convex'),assisted=False,robot_model=self.robot_model,robot_joints=dict(zip(result.get('joint_names',[]),result.get('joint_positions',[]))),wheel_angles=result.get('diagnostics',{}).get('wheel_angles'))
        diagnostics=dict(result.get('diagnostics',{}))
        diagnostics.update(phase=self.phase,destination=self.destination,route=[list(p) for p in self.path],
            requested_velocity=self.last_requested.tolist(),actual_velocity=[*result['velocity'][:2],result['yaw_rate']],
            velocity_frame='robot',tilt=result['tilt'],policy_status='failed' if self._policy_failed else 'running',
            failure_code=self.failure_code,physics_ms=result['physics_ms'],policy_ms=result['policy_ms'],
            physics_realtime_factor=1000*self.sim.control_dt/result['physics_ms'] if result['physics_ms']>0 else None,
            render_ms=None,route_recoveries=self.route_recoveries,manual_stop_latency_ms=self.manual_stop_latency_ms,
            manual_settle_ms=self.manual_settle_ms)
        state.update(control_mode='manual' if self.phase=='manual' else ('automatic' if self.path or self.interactive.active else 'idle'),
            manual_control=dict(sequence=self.manual_seq,requires_new_press=self._manual_expired,valid=self.phase=='manual' and time.monotonic()<self.manual_deadline,
                remaining_ms=max(0,(self.manual_deadline-time.monotonic())*1000)),diagnostics=diagnostics)
        state.update(language=self.language,ready_for_visit=self.ready_for_visit(),failure_code=self.failure_code,message_key=message_key(self.message))
        state['message']=localize(self.message,self.language);state['error']=localize(self.error,self.language)
        state['interactive']['reason']=localize(state['interactive']['reason'],self.language)
        state['conversation']['handoff']=localize(state['conversation']['handoff'],self.language)
        with self.lock:self.state=state
    def pose_target(self,target):
        if self.gesture_until:
            progress=4-(self.gesture_until-self.sim.data.time)
            blend=min(1,max(0,progress),max(0,self.gesture_until-self.sim.data.time))
            target[22]=target[22]*(1-blend)-.65*blend
            target[23]=target[23]*(1-blend)-.35*blend
            target[25]=target[25]*(1-blend)+.8*blend
        return target
    def close(self):
        self.interactive.finish_report('closed');self.sim.close()

