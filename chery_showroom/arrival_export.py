"""Scenario export on the existing renderer, physics owner and cinematic entry point."""
import json
import time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .arrival import SCRIPT,DURATION
from .rendering import create_renderer,options
from .voice_assets import CACHE,validate,mix


def stamp(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def subtitles(destination):
    lines=[]
    for i,cue in enumerate(SCRIPT['cues'],1):
        speaker='Robot' if cue['speaker']=='robot' else 'Customer'
        lines.append(f'{i}\n{stamp(cue["start"])} --> {stamp(cue["end"])}\n{speaker}: {cue["en"]}\n')
    Path(destination).write_text('\n'.join(lines),encoding='utf-8')


FONT=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
SMALL=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)


def overlay(frame,t,ai_generated=True):
    im=Image.fromarray(frame);draw=ImageDraw.Draw(im)
    draw.rectangle((0,0,960,29),fill='#111b23')
    label='MALONI ROBOTICS | SIMULATION | '+('AI-GENERATED ENGLISH VOICES' if ai_generated else 'ENGLISH VOICE-OVER')
    draw.text((16,6),label,font=SMALL,fill='#e7eced')
    draw.text((854,6),f'{min(55,int(t)):02d} / 55 s',font=SMALL,fill='#e7eced')
    cue=next((c for c in SCRIPT['cues'] if c['start']<=t<c['end']),None)
    if cue:
        text=('Robot: ' if cue['speaker']=='robot' else 'Customer: ')+cue['en']
        lines=['']
        for word in text.split():
            proposed=(lines[-1]+' '+word).strip()
            if draw.textlength(proposed,font=FONT)>884:lines.append(word)
            else:lines[-1]=proposed
        height=len(lines)*29+20;draw.rectangle((20,540-height-12,940,528),fill='#111b23')
        for i,line in enumerate(lines):
            width=draw.textlength(line,font=FONT)
            draw.text(((960-width)/2,540-height-2+i*29),line,font=FONT,fill='white')
    return np.asarray(im)


def checked_tick(app):
    app.last_client=time.monotonic();app.tick()
    if app.error or app.demo.status=='failed':raise RuntimeError(app.message or app.error)
    if not np.isfinite(app.sim.data.qpos).all() or app.sim.snapshot()['fallen']:
        raise RuntimeError('Demo robot lost numerical/physical stability.')
    for contact in app.sim.data.contact[:app.sim.data.ncon]:
        bodies=[int(app.sim.model.geom_bodyid[g]) for g in (contact.geom1,contact.geom2)]
        if 0 in bodies and bodies[0]!=bodies[1]:
            static=contact.geom1 if bodies[0]==0 else contact.geom2
            if app.sim.model.geom(static).name!='floor':raise RuntimeError('Robot touched showroom equipment.')


def finish_check(app):
    s=app.demo.snapshot()
    if s['status']!='completed' or s['arrived_at'] is None or s['arrived_at']>34 or s['min_separation']<1.2:
        raise RuntimeError('Customer arrival scenario failed acceptance: '+json.dumps(s))
    if sum(e['event']=='customer_entered_zone' for e in s['events'])!=1:
        raise RuntimeError('Expected one customer trigger.')
    presentation=next(e['time'] for e in s['events'] if e['event']=='presentation_started')
    if presentation>SCRIPT['cues'][3]['start']:raise RuntimeError('Voice would start before physical presentation approval.')
    return s


def export(video,quality='interactive',backend='classic',audio_dir=CACHE,fps=24):
    # Fail before compiling/rendering anything if the complete English soundtrack is missing.
    manifest=validate(audio_dir)
    from .runtime import Showroom
    import imageio_ffmpeg
    video=Path(video);video.parent.mkdir(parents=True,exist_ok=True)
    staged=video.with_name(video.stem+'.incomplete.mp4')
    soundtrack=mix(video.with_suffix('.wav'),audio_dir)
    srt=video.with_suffix('.en.srt');subtitles(srt)
    app=Showroom(quality);renderer=None;writer=None;started=time.perf_counter()
    try:
        app.demo.start();checked_tick(app)
        renderer=create_renderer(app.sim.model,540,960,backend)
        writer=imageio_ffmpeg.write_frames(str(staged),(960,540),fps=fps,codec='libx264',quality=8,
            macro_block_size=2,audio_path=str(soundtrack),audio_codec='aac',
            output_params=['-movflags','+faststart','-t',str(DURATION)])
        writer.send(None)
        captures={round(t*fps):t for t in (4,8,24,36,43,52)}
        for i in range(round(DURATION*fps)):
            t=i/fps
            while app.sim.data.time-app.demo.started<t-1e-8:checked_tick(app)
            renderer.update_scene(app.sim.data,camera='cinematic',scene_option=options('cinematic'))
            if backend=='filament' and i in {round(at*fps) for at in (6,12,34,41,46)}:
                for _ in range(7):renderer.render()
            frame=overlay(renderer.render(),t,manifest.get('ai_generated',False))
            writer.send(frame)
            if i in captures:Image.fromarray(frame).save(video.with_name(f'arrival_{captures[i]:02}.png'))
            if i%(fps*5)==0:print(f'Rendered {t:.0f}/{DURATION:.0f} s',flush=True)
        while app.demo.active:checked_tick(app)
        report=finish_check(app)
        writer.close();writer=None
        report.update(video=str(video),duration=DURATION,fps=fps,frames=round(DURATION*fps),resolution=[960,540],
                      renderer=backend,quality=quality,lighting='daylight_key_with_fill',audio_manifest=manifest,
                      wall_seconds=time.perf_counter()-started)
        staged.replace(video)
        video.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(video,flush=True)
        return report
    finally:
        if writer:writer.close()
        if renderer:renderer.close()
        app.close()
        staged.unlink(missing_ok=True)


def review(output,runs=3,render=False,backend='classic'):
    from .runtime import Showroom
    output=Path(output);output.mkdir(parents=True,exist_ok=True);reports=[]
    for run in range(runs):
        app=Showroom();renderer=None;captured=set()
        try:
            app.demo.start()
            if render and run==0:renderer=create_renderer(app.sim.model,540,960,backend)
            while app.demo.active:
                checked_tick(app)
                t=app.demo.elapsed
                for at in (4,8,24,36,43,52):
                    if renderer and t>=at and at not in captured:
                        renderer.update_scene(app.sim.data,camera='cinematic',scene_option=options('cinematic'))
                        Image.fromarray(overlay(renderer.render(),t)).save(output/f'arrival_{at:02}.png');captured.add(at)
            report=finish_check(app);reports.append(report)
            print(f'Run {run+1}: arrived {report["arrived_at"]:.2f}s; minimum separation {report["min_separation"]:.3f}m; completed 55s',flush=True)
        finally:
            if renderer:renderer.close()
            app.close()
    (output/'acceptance.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
    subtitles(output/'customer_arrival.en.srt')
    return reports


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).with_name('assets')/'review'/'arrival')
    p.add_argument('--runs',type=int,default=3);p.add_argument('--render',action='store_true');p.add_argument('--renderer',choices=['classic','filament'],default='classic')
    args=p.parse_args();review(args.output,args.runs,args.render,args.renderer)
if __name__=='__main__':main()
