import hashlib
import json
import re
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from chery_showroom.reception import ReceptionDesk
from chery_showroom.web_assets import asset_response, DIST


class ReceptionTests(unittest.TestCase):
    def test_answers_and_validation(self):
        desk = ReceptionDesk()
        answer = desk.respond(dict(text='Jakou barvu má CHERY?',car='tiggo8',run_id='a'),'a')
        self.assertIn('CHERY',answer['reply'])
        self.assertEqual(answer['run_id'],'a')
        answer = desk.respond(dict(text='Kolik stojí auto?',car='tiggo8',run_id='a'),'a')
        self.assertIn('verif',answer['reply'])
        for text in ['', ' '*4, 'a'*1001, None, 42]:
            with self.assertRaises(ValueError):desk.respond(dict(text=text,car='tiggo8',run_id='a'),'a')
        with self.assertRaises(ValueError):desk.respond(dict(text='Ahoj',car='tiggo8',run_id='a'),'b')
        desk.respond(dict(text='Dobrý den',car='tiggo8',run_id='b'),'b')
        self.assertEqual(desk.run_id,'b')

    def test_humanoid_asset_and_provenance(self):
        manifest = json.loads((DIST/'humanoid-assets.json').read_text())
        code,raw,mime=asset_response('/graphics/staff/g1-reception.glb')
        self.assertEqual(code,200);self.assertEqual(raw[:4],b'glTF')
        self.assertEqual(asset_response('/web/models/g1-reception.glb')[1],raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['sha256'])
        self.assertGreater(manifest['triangles'],100000)
        self.assertTrue(1.25 < manifest['bounds'][1][1]-manifest['bounds'][0][1] < 1.4)
        self.assertIn('BSD 3-Clause',(DIST/'UNITREE_LICENSE.txt').read_text())
        for path in ['/graphics/staff/../../runtime.py','/graphics/staff/g1-source.xml']:
            self.assertEqual(asset_response(path)[0],404)

    def test_authenticated_http_without_motion_or_lease_side_effects(self):
        from chery_showroom.runtime import server
        app=SimpleNamespace(run_id='test',last_client=0,lock=threading.RLock(),state={},frame=None,command=Mock())
        with patch('chery_showroom.voice.ShowroomProvider') as provider, patch('chery_showroom.credentials.api_key',return_value=None):
            provider.return_value.configured=False;http=server(app);base='http://127.0.0.1:'+str(http.server_port)
            try:
                token=re.search("const token='([^']+)'",urlopen(base+'/').read().decode())[1]
                def ask(value,auth=True):
                    headers={'Content-Type':'application/json'}
                    if auth:headers['X-Showroom-Token']=token
                    return urlopen(Request(base+'/reception/chat',data=json.dumps(value).encode(),headers=headers))
                value=dict(text='Jakou barvu má CHERY?',car='tiggo8',run_id='test')
                with self.assertRaises(HTTPError) as error:ask(value,False)
                self.assertEqual(error.exception.code,403)
                self.assertIn('CHERY',json.load(ask(value))['reply'])
                for text in ['ukaž mi CHERY','ano','stop','pozdrav']:
                    value['text']=text;self.assertEqual(ask(value).status,200)
                value['run_id']='old'
                with self.assertRaises(HTTPError) as error:ask(value)
                self.assertEqual(error.exception.code,400)
                app.command.assert_not_called();self.assertEqual(app.last_client,0)
            finally:
                http.shutdown();http.server_close();http.close_sessions()
