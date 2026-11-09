"""Automotive showroom: existing design, local native physics, no MuJoCo runtime."""
import argparse,json,math,time
from pathlib import Path
from .controller import Showroom
from .http_server import server
from .browser import open_panel

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robot',choices=['g1','maloni120'],default='maloni120')
    parser.add_argument('--headless',action='store_true');parser.add_argument('--duration',type=float,default=60)
    parser.add_argument('--port',type=int,default=8765);parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--scenario',choices=['customer_arrival']);parser.add_argument('--tour',choices=['reception','entrance','waiting_area','tiggo4','tiggo7','tiggo8','vehicle_1','vehicle_2','vehicle_3'])
    parser.add_argument('--quality',choices=['interactive','presentation'],default='interactive')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--language',choices=['cs','en'],default='cs')
    parser.add_argument('--visit-log',type=Path,default=Path('build/showroom-native/visits.jsonl'))
    args=parser.parse_args()
    if not math.isfinite(args.duration) or args.duration<=0:parser.error('Duration must be finite and positive')
    if not 0<=args.port<=65535:parser.error('Port must be between 0 and 65535')
    app=None;http=None;started=time.monotonic()
    try:
        app=Showroom(args.quality,language=args.language,visit_log=args.visit_log,robot_model=args.robot);app.tick()
        if args.scenario:app.demo.start()
        if args.tour:
            from .layout import VEHICLE_SITES
            app.command(dict(action='navigate',target=VEHICLE_SITES.get(args.tour,args.tour)))
        if not args.headless:
            http=server(app,args.port);url=f'http://127.0.0.1:{http.server_port}'
            print('MALONI automotive showroom: '+url,flush=True)
            if not args.no_browser:open_panel(url)
        start_sim=app.sim.data.time;disconnected=False
        while not args.headless or app.sim.data.time-start_sim<args.duration:
            begin=time.monotonic()
            if args.headless:app.last_client=begin
            # Retain the scene when the browser closes; do not burn CPU on a hidden showroom.
            if not args.headless and begin-app.last_client>3:
                if not disconnected and (app.path or app.gesture_until or any(app.manual) or app.interactive.active or app.demo.active):
                    app.fail('Dashboard connection lost.');app.tick()
                disconnected=True
                time.sleep(.05);continue
            disconnected=False
            app.tick()
            if args.headless and args.scenario and app.demo.status in ('completed','failed','stopped'):break
            if args.headless and args.tour and not app.path:break
            if not args.headless:time.sleep(max(0,.02-(time.monotonic()-begin)))
        success=not app.error and (not args.scenario or app.demo.status=='completed') and (not args.tour or app.phase=='arrived')
        result=dict(success=bool(success),backend=app.state['backend'],state=app.state,wall_seconds=time.monotonic()-started,profile=app.sim.world.profile())
        if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
        if not success:return 1
        return 0
    except KeyboardInterrupt:return 0
    except (RuntimeError,ValueError,OSError) as e:parser.exit(1,f'Showroom could not start: {e}\n')
    finally:
        if http:http.shutdown();http.server_close();http.close_sessions()
        if app:app.close()
if __name__=='__main__':raise SystemExit(main())
