"""Existing showroom HTTP API, independent of any physics or rendering engine."""
import json
import queue
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .arrival_script import SCRIPT
WEB=Path(__file__).with_name('panel.html')

def server(app, port=0):
    from .voice import ShowroomProvider
    from .credentials import api_key
    provider=ShowroomProvider(key=api_key());sessions={};session_lock=threading.Lock();voice_closing=threading.Event()
    from .reception import ReceptionDesk
    reception=ReceptionDesk()
    token=secrets.token_urlsafe(24)
    audio_cache={'until':0.,'ready':False};audio_lock=threading.Lock()
    def cached_audio_ready():
        with audio_lock:
            now=time.monotonic()
            if now>=audio_cache['until']:
                from .voice_assets import CACHE,validate
                try:validate(CACHE);audio_cache['ready']=True
                except ValueError:audio_cache['ready']=False
                audio_cache['until']=now+5
            return audio_cache['ready']
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def setup(self):
            super().setup();self.connection.settimeout(5)
        def local_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        def send(self,status,data,kind='application/json'):
            # Static assets are already encoded, including JSON layout and fonts.
            raw=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if not self.local_host():return self.send(403,{'error':'Invalid local host.'})
            if self.path=='/favicon.ico':return self.send(204,b'','image/x-icon')
            from .web_assets import asset_response,layout_payload
            if self.path=='/graphics/layout.json' and hasattr(getattr(app,'sim',None),'definition'):
                return self.send(200,layout_payload(app.sim.definition))
            graphic = asset_response(self.path)
            if graphic is not None:
                return self.send(*graphic)
            if self.path=='/arrival.js':
                from .arrival_script import SCRIPT
                raw=WEB.with_name('arrival.js').read_text().replace('__ARRIVAL_CUES__',json.dumps(SCRIPT['cues'],ensure_ascii=False)).encode()
                return self.send(200,raw,'application/javascript')
            if self.path=='/interactive.js':return self.send(200,WEB.with_name('interactive.js').read_bytes(),'application/javascript')
            if self.path=='/voice.js':return self.send(200,WEB.with_name('voice.js').read_bytes(),'application/javascript')
            if self.path=='/browser_voice.js':return self.send(200,WEB.with_name('browser_voice.js').read_bytes(),'application/javascript')
            if self.path=='/messages.json':return self.send(200,WEB.with_name('messages.json').read_bytes(),'application/json')
            if self.path=='/operator.js':return self.send(200,WEB.with_name('operator.js').read_bytes(),'application/javascript')
            if self.path=='/locale.js':return self.send(200,WEB.with_name('locale.js').read_bytes(),'application/javascript')
            if self.path=='/':return self.send(200,WEB.read_bytes().replace(b'__TOKEN__',token.encode()),'text/html; charset=utf-8')
            if self.headers.get('X-Showroom-Token')!=token:return self.send(403,{'error':'Access denied.'})
            if self.path.startswith('/demo-audio/'):
                from .voice_assets import CACHE,validate
                from .arrival_script import SCRIPT
                name=self.path.split('/')[-1]
                if name not in {c['id']+'.wav' for c in SCRIPT['cues']}:return self.send(404,{})
                try:validate(CACHE);raw=(CACHE/name).read_bytes()
                except (ValueError,OSError):return self.send(409,{'error':'English audio clips are not prepared.'})
                return self.send(200,raw,'audio/wav')
            if self.path=='/frame':
                with app.lock:frame=app.frame
                return self.send(200,frame,'image/jpeg') if frame else self.send(409,{'error':'The camera is not ready.'})
            if self.path!='/state':return self.send(404,{})
            app.last_client=time.monotonic()
            audio_ready=cached_audio_ready()
            with app.lock:state=dict(app.state,language=getattr(app,'language','en'),voice_configured=provider.configured,demo_audio_ready=audio_ready,demo_audio_language='en',camera_ready=bool(app.frame),reception_available=True)
            return self.send(200,state)
        def do_POST(self):
            if not self.local_host():return self.send(403,{'error':'Invalid local host.'})
            if self.headers.get('X-Showroom-Token')!=token:return self.send(403,{})
            if self.path not in ('/action','/session','/cancel','/reception/chat'):return self.send(404,{})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<(131072 if self.path=='/session' else 8192):raise ValueError('Invalid size.')
                v=json.loads(self.rfile.read(n))
                if not isinstance(v,dict):raise ValueError('Invalid request.')
                if self.path=='/reception/chat':
                    with app.lock:run_id=app.run_id;context=dict(app.state.get('conversation') or {},robot_model=app.state.get('robot_model'))
                    result=reception.respond(v,run_id,getattr(app,'language','en'),context)
                    if app.run_id!=run_id:raise ValueError('The scene was reset.')
                    return self.send(200,result)
                if self.path=='/session':
                    if not isinstance(v.get('sdp'),str):raise ValueError('Missing SDP.')
                    with app.lock:context=dict(app.state)
                    if v.get('run_id')!=context['run_id']:raise ValueError('The scene was reset.')
                    result=provider.create(v['sdp'],context);sid=result['session']['id']
                    with session_lock:sessions[sid]=context['run_id']
                    if app.run_id!=context['run_id']:
                        provider.hangup(sid)
                        with session_lock:sessions.pop(sid,None)
                        raise ValueError('The scene was reset.')
                    return self.send(200,{'sdp':result['transport']['sdp'],'session_id':sid})
                if self.path=='/cancel':
                    sid=v.get('session_id')
                    with session_lock:
                        owned=sid in sessions
                        owner=sessions.pop(sid,None)
                    if owner==app.run_id and not v.get('interruption',False):app.commands.put(('stop',app.selected,'',owner))
                    if owned:provider.hangup(sid)
                    return self.send(200,{'ok':owned})
                app.command(v);self.send(202,{'queued':True})
            except (ValueError,TypeError) as e:self.send(400,{'error':str(e)})
            except RuntimeError as e:self.send(502,{'error':str(e)})
    http=ThreadingHTTPServer(('127.0.0.1',port),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
    def reap_sessions():
        while not voice_closing.wait(.5):
            with session_lock:
                stale=[sid for sid,run in sessions.items() if run!=app.run_id or time.monotonic()-app.last_client>3]
                for sid in stale:sessions.pop(sid,None)
            for sid in stale:provider.hangup(sid)
    threading.Thread(target=reap_sessions,daemon=True).start()
    def close_sessions():
        voice_closing.set()
        with session_lock:pending=list(sessions);sessions.clear()
        for sid in pending:provider.hangup(sid)
    http.close_sessions=close_sessions
    return http

