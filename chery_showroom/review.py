"""Reproducible real render evidence and separate physics/render timing report."""
import argparse,json,platform,time,resource,os
from pathlib import Path
import mujoco
import numpy as np
from PIL import Image
from .runtime import Showroom
from .rendering import create_renderer,options

def main():
    p=argparse.ArgumentParser();p.add_argument('--renderer',choices=['classic','filament'],default='classic');p.add_argument('--quality',choices=['interactive','presentation'],default='interactive');p.add_argument('--width',type=int,default=960);p.add_argument('--height',type=int,default=540);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);app=Showroom(args.quality);r=None;frames=[];steps=[];navigation=[]
    report=dict(renderer=args.renderer,quality=args.quality,resolution=[args.width,args.height],mujoco=mujoco.__version__,os=platform.platform(),cpu=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unknown'),physical_gpu='Not exposed; PCI/nvidia tools and /dev/dri are unavailable.',renderer_device='Vulkan llvmpipe (see renderer log)' if args.renderer=='filament' else '')
    def tick():
        app.last_client=time.monotonic();app.tick();steps.append(dict(physics_ms=app.state['physics_ms'],policy_ms=app.state['policy_ms']))
        if app.error or not np.isfinite(app.sim.data.qpos).all():raise RuntimeError(app.error or 'Non-finite state')
        for i in range(app.sim.data.ncon):
            c=app.sim.data.contact[i];bodies=[int(app.sim.model.geom_bodyid[g]) for g in (c.geom1,c.geom2)]
            if (0 in bodies) and bodies[0]!=bodies[1]:
                static=c.geom1 if bodies[0]==0 else c.geom2
                if app.sim.model.geom(static).name!='floor':raise RuntimeError('Robot touched static obstacle: '+str(app.sim.model.geom(static).name))
    def travel(target):
        start=time.perf_counter();sim_start=app.sim.data.time;app.command(dict(action='navigate',target=target))
        for _ in range(7500):
            tick()
            if not app.path:break
        else:raise RuntimeError('Navigation timeout: '+target)
        for _ in range(40):tick()
        navigation.append(dict(target=target,phase=app.phase,position=app.sim.data.qpos[:3].tolist(),sim_seconds=app.sim.data.time-sim_start,wall_seconds=time.perf_counter()-start))
    def capture(camera,name=None):
        r.update_scene(app.sim.data,camera=camera,scene_option=options(camera));start=time.perf_counter();image=r.render();elapsed=time.perf_counter()-start
        Image.fromarray(image).save(args.output/((name or camera)+'.png'));frames.append(dict(camera=camera,readback_ms=elapsed*1000))
    started=time.perf_counter()
    try:
        for _ in range(100):tick()
        r=create_renderer(app.sim.model,args.height,args.width,args.renderer)
        if args.renderer=='classic':
            from OpenGL import GL
            report['renderer_device']=GL.glGetString(GL.GL_RENDERER).decode()
        # Warm shader/resource paths, then measure complete update+render/readback frames.
        for _ in range(3):r.update_scene(app.sim.data,camera='vehicle_demo_view',scene_option=options('vehicle_demo_view'));r.render()
        timing=[]
        for _ in range(8):
            start=time.perf_counter();r.update_scene(app.sim.data,camera='vehicle_demo_view',scene_option=options('vehicle_demo_view'));r.render();timing.append(time.perf_counter()-start)
        report['render_benchmark']=dict(warmup_frames=3,measured_frames=8,mean_ms=float(np.mean(timing)*1000),median_ms=float(np.median(timing)*1000),fps=float(1/np.mean(timing)),physics_paused=True,included='scene update, rendering and CPU pixel readback; excludes PNG encoding')
        capture('reception_view');capture('furniture_detail');capture('entrance','glazed_facade');capture('showroom_overview')
        travel('entrance');travel('reception');travel('waiting_area');travel('vehicle_3')
        capture('vehicle_demo_view');capture('detail_view');capture('entrance_view')
        report['physics']=dict(control_steps=len(steps),simulated_seconds=float(app.sim.data.time),mean_physics_ms=float(np.mean([v['physics_ms'] for v in steps])),mean_policy_ms=float(np.mean([v['policy_ms'] for v in steps])),finite=True,fallen=app.sim.snapshot()['fallen'],navigation=navigation)
        report['frames']=frames;report['total_wall_seconds']=time.perf_counter()-started;report['peak_process_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:
        if r:r.close()
        app.close()
if __name__=='__main__':main()
