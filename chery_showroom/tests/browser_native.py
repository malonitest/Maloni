"""Run the real showroom and its browser acceptance locally, without cloud calls."""
import os
from pathlib import Path
import subprocess
import threading
import time
from unittest.mock import patch
from chery_showroom.runtime import Showroom
from chery_showroom.http_server import server

ROOT=Path(__file__).resolve().parents[2]
def main():
    node=os.environ.get('NODE_EXECUTABLE','node')
    app=Showroom();app.tick();stop=threading.Event();http=None;owner=None
    try:
        with patch('chery_showroom.credentials.api_key',return_value=''):http=server(app)
        def run():
            while not stop.is_set():
                begin=time.monotonic();app.tick();stop.wait(max(0,.02-(time.monotonic()-begin)))
        owner=threading.Thread(target=run);owner.start()
        env=dict(os.environ,SHOWROOM_URL=f'http://127.0.0.1:{http.server_port}',REVIEW_OUTPUT=str(ROOT/'build/showroom-native/browser'))
        test=os.environ.get('SHOWROOM_BROWSER_TEST','native')
        if test not in ('native','bilingual','voice_runtime','operator','customer_gait','customer_gait_visual'):raise ValueError('Unknown browser test')
        if test=='voice_runtime':env['REVIEW_OUTPUT']=str(ROOT/'build/showroom-native/voice-runtime-bilingual.json')
        subprocess.run([node,str(ROOT/f'chery_showroom/web/tests/{test}.cjs')],cwd=ROOT,env=env,check=True,timeout=1200 if test=='customer_gait' else (600 if test=='bilingual' else 300))
    finally:
        stop.set()
        if owner:owner.join(timeout=10)
        if http:http.shutdown();http.server_close();http.close_sessions()
        app.close()
if __name__=='__main__':main()
