"""Single-owner physics, queued HTTP commands and leased autonomous navigation."""
import argparse,json,math,time,threading,queue,secrets,io,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from contextlib import nullcontext
import mujoco
import numpy as np
from benchmark_lab.core import Simulation
from benchmark_lab.velocity import KEY_COMMANDS
from .scene import build,STOPS
from .layout import WAYPOINTS,VEHICLE_SITES,CAMERAS,CARS
from .navigation import Navigator
from .rendering import create_renderer,options as render_options
from .sales import CATALOG,Visit,car_entry
from .cinematic import update as update_cinematic
from .arrival import ArrivalDemo
from .browser import open_panel
from .interactive import InteractiveVisit
WEB=Path(__file__).with_name('panel.html')

class Showroom:
    def __init__(self,quality="interactive"):
        self.sim=Simulation(model=mujoco.MjModel.from_xml_path(str(build(quality))))
        self.navigator=Navigator(self.sim.model)
        self.demo=ArrivalDemo(self)
        self.interactive=InteractiveVisit(self)
        self.frame=None;self.camera_view='robot';self.camera_enabled=False;self.commands=queue.Queue();self.lock=threading.Lock();self.last_client=time.monotonic();self.selected='tiggo4';self.message='Welcome to the MALONI Robotics automotive showroom. Independent simulation demonstration.';self.revision=0;self.reset()
    def reset(self):
        self.sim.reset({'control':'velocity'});self.sim.data.qpos[:2]=STOPS['reception'];mujoco.mj_forward(self.sim.model,self.sim.data)
        self.demo.reset()
        self.interactive.reset()
        self.visit=Visit();self.selected=self.visit.selected;self.message=self.visit.message;self.gesture_kind='present';self.manual=np.zeros(3);self.destination='reception';self.frame=None;self.run_id=uuid.uuid4().hex;self.path=[];self.phase='greeting';self.gesture_until=0;self.error='';self.last_progress=self.sim.data.time;self.best=1e9
    def stop(self):self.path=[];self.manual[:]=0;self.gesture_until=0;self.phase='stopped'
    def reply(self,result):
        self.message,self.selected,action=result
        return action
    def fail(self,message):
        self.stop()
        if self.error==message and self.visit.stage=='paused':return
        if self.interactive.active:self.interactive.pause(message)
        self.error=message
        self.reply(self.visit.interrupted(message+' We can continue our conversation here.'))
    def facing_vehicle(self,car):
        delta=np.array(CARS[car][:2])-self.sim.data.qpos[:2]
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
        if car not in STOPS or car=='reception':raise ValueError('Unknown car.')
        if a not in ('select','escort','present','stop','reset','chat','reception','camera','view','navigate','advice','quick','entertainment','handoff','greet','scenario','interactive_start','customer','interactive_continue','interactive_camera'):raise ValueError('Unknown action.')
        if a=='scenario' and v.get('scenario','customer_arrival')!='customer_arrival':raise ValueError('Unknown scenario.')
        if a=='navigate' and v.get('target') not in WAYPOINTS:raise ValueError('Unknown navigation target.')
        accepted_run=self.run_id
        if v.get('run_id',accepted_run)!=accepted_run:raise ValueError('The scene was reset; refresh the panel state.')
        if a=='customer' and v.get('text') not in ('approach','follow','stop','exit'):raise ValueError('Unknown customer target.')
        if a=='interactive_camera' and v.get('text') not in ('on','off'):raise ValueError('Unknown camera mode.')
        self.commands.put((a,car,str(v.get('target') if a=='navigate' else v.get('text',''))[:2000],accepted_run))
    def tick(self):
        while not self.commands.empty():
            queued=self.commands.get_nowait()
            if len(queued)==4:
                a,car,text,run=queued
                if run!=self.run_id:continue
            else:a,car,text=queued
            if a=='scenario':self.demo.start();continue
            if a=='interactive_escort':
                if not self.interactive.active or self.interactive.stage!='escort' or text!=self.run_id:continue
                a='escort';interactive_internal=True
            else:interactive_internal=False
            if not interactive_internal and self.interactive.handle(a,text):continue
            internal=a in ('demo_escort','demo_present','demo_greet')
            if internal:
                if not self.demo.active or text!=self.run_id:continue
                a=a.removeprefix('demo_')
            if self.demo.active and not internal and a not in ('camera','view'):
                self.demo.cancel()
            if a=='manual':
                self.stop();self.visit.cancel();self.manual[:]=KEY_COMMANDS[int(text)];self.phase='manual';continue
            if a=='camera':self.camera_enabled=text=='on';continue
            if a=='view':
                if text in CAMERAS:self.camera_view=text;self.frame=None
                continue
            if a=='chat':
                # Any utterance cancels an active gesture/presentation before processing.
                self.gesture_until=0
                if self.phase=='presentation':self.phase='consultation'
                previous=self.selected
                a=self.reply(self.visit.respond(text,self.selected,self.sim.data.time));car=self.selected
                if previous!=self.selected or self.visit.mode=='entertainment' or self.visit.stage=='handoff':self.stop()
                if a is None:continue
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
                try:self.path=self.navigator.route(self.sim.data.qpos[:2],target)
                except ValueError:
                    self.fail('I could not plan a safe route. Stopping.');continue
                self.error='';self.phase='escort';self.message=('Please follow me.' if self.demo.active else 'Please follow me. I will stop in front of the car for a clear view.') if self.destination in VEHICLE_SITES.values() else 'I will move to the selected location.';self.visit.message=self.message;self.visit.serial+=1;self.last_progress=self.sim.data.time;self.best=1e9
            if a=='present':
                if self.error:self.message='Please reset the simulation first.'
                elif np.linalg.norm(self.sim.data.qpos[:2]-STOPS[car])>.55:self.message='Please complete the escort to this car first.'
                elif self.path or np.any(self.manual) or np.linalg.norm(self.sim.data.qvel[:2])>.15 or abs(self.sim.snapshot()['yaw_rate'])>.15:self.message='The presentation can start once we have stopped.'
                elif not self.facing_vehicle(car):self.message='Please complete the escort and turn towards the car first.'
                else:self.selected=car;self.visit.selected=car;self.phase='presentation';self.gesture_kind='present';self.gesture_until=self.sim.data.time+4;self.reply(self.visit.present(self.sim.data.time))
        self.demo.update()
        self.interactive.update()
        if self.message!=self.visit.message:self.reply(self.visit.say(self.message))
        s=self.sim.snapshot();cmd=self.manual.copy() if self.phase=='manual' else np.zeros(3)
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
            if dist<.25:
                if len(self.path)==1:self.phase='aligning'
                else:self.path.pop(0)
                self.best=1e9;self.last_progress=self.sim.data.time
            else:
                w,x,y,z=s['orientation'];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));heading=math.atan2(delta[1],delta[0]);err=math.atan2(math.sin(heading-yaw),math.cos(heading-yaw))
                cmd[2]=np.clip(err,-.35,.35)
                if abs(err)<.3:cmd[0]=min(.22,dist*.5)
                if dist<self.best-.04:self.best=dist;self.last_progress=self.sim.data.time
                if self.sim.data.time-self.last_progress>35:self.fail('The route is blocked or no progress is being made. Stopping.');cmd[:]=0
        if self.phase=='aligning':
            if self.destination in VEHICLE_SITES.values():
                key=next(k for k,v in VEHICLE_SITES.items() if v==self.destination);look=np.array(CARS[key][:2])
            else:look=np.array({'reception':(-5,-3.7),'entrance':(0,0),'waiting_area':(6.5,-3.7)}[self.destination])
            delta=look-self.sim.data.qpos[:2];w,x,y,z=s['orientation']
            yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));heading=math.atan2(delta[1],delta[0]);err=math.atan2(math.sin(heading-yaw),math.cos(heading-yaw))
            cmd[2]=np.clip(err,-.35,.35)
            error=np.array(self.path[-1])-self.sim.data.qpos[:2]
            c,sn=math.cos(yaw),math.sin(yaw)
            local=np.array([[c,sn],[-sn,c]])@error
            cmd[:2]=np.clip(.6*local,-.13,.13)
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
        self.sim.pose_target=self.pose_target
        result=self.sim.step(cmd)
        if self.gesture_until:
            if self.sim.data.time>=self.gesture_until:
                self.gesture_until=0
                if self.phase!='stopped':self.phase='consultation'
        camera=self.sim.model.camera('robot').id
        self.sim.model.cam_pos[camera]=self.sim.data.qpos[:3]+[0,0,.48]
        w,x,y,z=self.sim.data.qpos[3:7]
        yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        base=np.array([.5,.5,-.5,-.5])
        mujoco.mju_mulQuat(self.sim.model.cam_quat[camera],np.array([math.cos(yaw/2),0,0,math.sin(yaw/2)]),base)
        mujoco.mj_forward(self.sim.model,self.sim.data)
        update_cinematic(self.sim.model,self.sim.data,self.sim.data.time)
        self.demo.camera()
        if self.error and self.demo.active:self.demo.cancel('failed')
        self.revision+=1
        with self.lock:self.state=dict(run_id=self.run_id,position=result['position'],phase=self.phase,selected=self.selected,message=self.message,error=self.error,revision=self.revision,camera_view=self.camera_view,destination=self.destination,waypoints={name:self.sim.model.site(name).pos[:2].tolist() for name in WAYPOINTS},sim_time=result['sim_time'],physics_ms=result['physics_ms'],policy_ms=result['policy_ms'],gesture=bool(self.gesture_until),conversation=self.visit.snapshot(),message_id=self.visit.serial,catalog=CATALOG,demo=self.demo.snapshot(),interactive=self.interactive.snapshot())
    def pose_target(self,target):
        if self.gesture_until:
            progress=4-(self.gesture_until-self.sim.data.time)
            blend=min(1,max(0,progress),max(0,self.gesture_until-self.sim.data.time))
            target[22]=target[22]*(1-blend)-.65*blend
            target[23]=target[23]*(1-blend)-.35*blend
            target[25]=target[25]*(1-blend)+.8*blend
        return target
    def close(self):self.sim.close()

from .http_server import server

def main():
    p=argparse.ArgumentParser();p.add_argument('--scenario',choices=['customer_arrival']);p.add_argument('--headless',action='store_true');p.add_argument('--duration',type=float,default=60);p.add_argument('--preview',action='store_true');p.add_argument('--tour',choices=list(dict.fromkeys([*STOPS,*WAYPOINTS])));p.add_argument('--quality',choices=['interactive','presentation'],default='interactive');p.add_argument('--renderer',choices=['classic','filament'],default='classic',help='Offscreen previews/export backend; the existing viewer stays classic OpenGL');p.add_argument('--output-dir',type=Path,help='Directory for preview images');p.add_argument('--cinematic',action='store_true',help='Smooth 40-second showroom tour');args=p.parse_args()
    app=Showroom(args.quality);http=None;viewer=None;renderer=None;last_frame=0;measure=[];beg=time.monotonic()
    try:
        app.camera_view='cinematic' if args.cinematic else 'showroom_overview'
        if args.scenario:app.demo.start()
        app.tick()
        if not args.headless and not args.preview:
            http=server(app)
            print(f'MALONI Robotics panel: http://127.0.0.1:{http.server_port}',flush=True)
        if args.preview:
            if args.tour:
                app.command(dict(action='navigate',target=VEHICLE_SITES.get(args.tour,args.tour)))
                for _ in range(7500):
                    app.last_client=time.monotonic();app.tick()
                    if app.error:raise RuntimeError(app.error)
                    if not app.path:break
                else:raise RuntimeError('Preview navigation did not complete.')
            from PIL import Image
            renderer=create_renderer(app.sim.model,height=720,width=1280,backend=args.renderer)
            output=args.output_dir or Path(__file__).with_name('assets');output.mkdir(parents=True,exist_ok=True)
            for camera in ('showroom_overview','entrance_view','reception_view','vehicle_demo_view','detail_view'):
                options=render_options(camera)
                renderer.update_scene(app.sim.data,camera=camera,scene_option=options);Image.fromarray(renderer.render()).save(output/(camera+'.png'))
            return
        if not args.headless:
            from mujoco import viewer as viewer_module
            viewer=viewer_module.launch_passive(app.sim.model,app.sim.data,key_callback=app.on_key)
            viewer.opt.geomgroup[4]=False;viewer.opt.geomgroup[5]=False
            viewer.cam.type=mujoco.mjtCamera.mjCAMERA_FIXED;viewer.cam.fixedcamid=app.sim.model.camera(app.camera_view).id
            viewer.cam.lookat[:]=(0,1,1);viewer.cam.distance=17;viewer.cam.azimuth=90;viewer.cam.elevation=-30
            open_panel(f'http://127.0.0.1:{http.server_port}')
        if args.tour:app.command(dict(action='navigate',target=VEHICLE_SITES.get(args.tour,args.tour)))
        start_sim=app.sim.data.time
        while (app.sim.data.time-start_sim<args.duration if args.headless else viewer.is_running()):
            t=time.monotonic()
            if args.headless:app.last_client=t
            with viewer.lock() if viewer else nullcontext():
                app.tick()
                if viewer:
                    viewer.cam.fixedcamid=app.sim.model.camera(app.camera_view).id
                    viewer.opt.geomgroup[4]=app.camera_view not in ('overview','showroom_overview')
            measure.append(app.state['physics_ms']+app.state['policy_ms'])
            if viewer and app.camera_enabled and t-last_frame>.5:
                from PIL import Image
                if renderer is None:renderer=create_renderer(app.sim.model,height=360,width=640,backend=args.renderer)
                options=render_options(app.camera_view)
                renderer.update_scene(app.sim.data,camera=app.camera_view,scene_option=options);buffer=io.BytesIO();Image.fromarray(renderer.render()).save(buffer,format='JPEG')
                with app.lock:app.frame=buffer.getvalue()
                last_frame=t
            if args.headless and args.scenario and app.demo.status in ('completed','failed','stopped'):break
            if viewer:viewer.sync();time.sleep(max(0,.02-(time.monotonic()-t)))
        print(json.dumps(dict(state=app.state,wall_seconds=time.monotonic()-beg,mean_step_ms=float(np.mean(measure))),ensure_ascii=False))
        if args.headless and args.scenario and app.demo.status!='completed':p.exit(1,'Scenario did not complete successfully.\n')
    finally:
        if renderer:renderer.close()
        if viewer:viewer.close()
        if http:http.shutdown();http.server_close();http.close_sessions()
        app.close()
if __name__=='__main__':main()
