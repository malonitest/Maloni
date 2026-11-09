"""Eye-level dolly camera in the actual MuJoCo scene; no generated imagery."""
from pathlib import Path
import argparse,math,time
import numpy as np
from .pose_math import matrix_quaternion, camera_sync
from .layout import CAMERAS,WAYPOINTS
DURATION=40.
POSITIONS=np.array([[-6,-1.5,1.8],[-2,-1.6,1.55],[2,-1.4,1.45],[5,-1.5,1.4],[7,-1.5,1.65],[3,-2.2,1.8],[-1,-1.8,1.8]])
TARGETS=np.array([[-2,3,1.1],[0,3.6,1.0],[6.3,3.6,1.0],[6.3,3.6,1.0],[6.3,3.6,1.1],[1,3.6,1.1],[-2,3.6,1.1]])

def spline(points,t):
    at=(t%DURATION)/DURATION*len(points);i=math.floor(at);u=at-i
    a,b,c,d=[points[(i+j)%len(points)] for j in (-1,0,1,2)]
    return .5*((2*b)+(-a+c)*u+(2*a-5*b+4*c-d)*u*u+(-a+3*b-3*c+d)*u*u*u)

def camera_pose(t):
    pos=spline(POSITIONS,t);target=spline(TARGETS,t);forward=target-pos;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    quaternion=matrix_quaternion(np.column_stack((right,up,-forward)))
    return pos,quaternion

def update(model,data,t):
    cam=model.camera('cinematic').id;pos,quat=camera_pose(t);model.cam_pos[cam]=pos;model.cam_quat[cam]=quat;camera_sync(model,data)

def main():
    from .rendering import create_renderer,options
    p=argparse.ArgumentParser();p.add_argument('--scenario',choices=['customer_arrival']);p.add_argument('--audio-dir',type=Path);p.add_argument('--video',type=Path);p.add_argument('--seconds',type=float,default=12);p.add_argument('--fps',type=int,default=24);p.add_argument('--renderer',choices=['classic','filament'],default='classic');p.add_argument('--camera',choices=CAMERAS,default='cinematic');p.add_argument('--demo-target',choices=list(WAYPOINTS));p.add_argument('--quality',choices=['interactive','presentation'],default='presentation');args=p.parse_args()
    if args.seconds<=0 or args.fps<=0:p.error('Duration and FPS must be positive.')
    if args.scenario:
        if not args.video:p.error('--scenario requires --video for cinematic export.')
        if args.demo_target:p.error('--scenario and --demo-target cannot be combined.')
        from .arrival_export import export
        from .voice_assets import CACHE
        export(args.video,args.quality,args.renderer,args.audio_dir or CACHE,args.fps)
        return
    from .runtime import Showroom
    from PIL import Image
    app=Showroom(args.quality);renderer=None;writer=None
    try:
        for _ in range(50):app.last_client=time.monotonic();app.tick()
        renderer=create_renderer(app.sim.model,height=540,width=960,backend=args.renderer)
        destination=Path(__file__).with_name('assets')
        if args.video:
            import imageio_ffmpeg
            args.video.parent.mkdir(parents=True,exist_ok=True)
            writer=imageio_ffmpeg.write_frames(str(args.video),(960,540),fps=args.fps,codec='libx264',quality=8,macro_block_size=2,output_params=['-movflags','+faststart'])
            writer.send(None)
            if args.demo_target:
                app.command(dict(action='navigate',target=args.demo_target));app.last_client=time.monotonic();app.tick()
            sim_start=app.sim.data.time
            for i in range(round(args.seconds*args.fps)):
                if args.demo_target:
                    while app.sim.data.time<sim_start+i/args.fps:
                        app.last_client=time.monotonic();app.tick()
                        if app.error:raise RuntimeError(app.error)
                update(app.sim.model,app.sim.data,4+i/args.fps);renderer.update_scene(app.sim.data,camera=args.camera,scene_option=options(args.camera));writer.send(renderer.render())
            print(args.video)
        else:
            for label,t in [('arrival',0),('chery',14),('detail',22)]:
                update(app.sim.model,app.sim.data,t);renderer.update_scene(app.sim.data,camera='cinematic',scene_option=options('cinematic'));Image.fromarray(renderer.render()).save(destination/('cinematic_'+label+'.png'))
    finally:
        if writer is not None:writer.close()
        if renderer is not None:renderer.close()
        app.close()
if __name__=='__main__':main()
