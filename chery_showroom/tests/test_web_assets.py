import json
import unittest
from chery_showroom.web_assets import asset_response

class GraphicsAssetsTests(unittest.TestCase):
    def test_layout_and_model(self):
        code, raw, mime = asset_response('/graphics/layout.json')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)['car']['length'], 4.72)
        vehicles = json.loads(raw)['vehicles']
        self.assertEqual(len(vehicles), 3)
        for vehicle in vehicles:
            self.assertEqual(asset_response(vehicle['url'])[1][:4], b'glTF')
        code, raw, mime = asset_response('/graphics/chery.glb')
        self.assertEqual(code, 200)
        self.assertEqual(raw[:4], b'glTF')
    def test_paths(self):
        for path in ['/web/../runtime.py', '/web/%2e%2e/runtime.py', '/web/%2fetc/passwd', '/graphics/runtime.py', '/web/a%5cb', '/web/%00', '/graphics/furniture/../provenance.json', '/graphics/furniture/unlisted.glb', '/graphics/materials/source.png']:
            with self.subTest(path=path): self.assertEqual(asset_response(path)[0],404)
        self.assertIsNone(asset_response('/state'))
        self.assertIsNone(asset_response('/action'))
    def test_bundle(self):
        self.assertEqual(asset_response('/web/')[0],200)
        self.assertEqual(asset_response('/graphics/studio.hdr')[0],200)
        self.assertEqual(asset_response('/web/missing.js')[0],404)

    def test_premium_assets_keep_source_materials_and_images(self):
        import hashlib
        import struct
        from pathlib import Path
        from PIL import Image
        from chery_showroom.web_assets import ROOT, DIST
        manifest = json.loads((DIST / 'premium-assets.json').read_text())
        self.assertEqual(len(manifest), 2)
        for item in manifest:
            model_name = Path(item['file']).stem
            code, raw, mime = asset_response('/graphics/furniture/' + model_name + '.glb')
            self.assertEqual(code, 200)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
            length = struct.unpack_from('<I', raw, 12)[0]
            doc = json.loads(raw[20:20+length])
            source_dir = ROOT / 'assets' / 'furnishings' / model_name
            original = json.loads((source_dir / (model_name + '.gltf')).read_text())
            self.assertEqual(doc['materials'], original['materials'])
            self.assertEqual(doc['meshes'], original['meshes'])
            binary = raw[28+length:]
            self.assertTrue(all('uri' not in b for b in doc['buffers']))
            for image, source in zip(doc['images'], original['images']):
                self.assertNotIn('uri', image)
                view = doc['bufferViews'][image['bufferView']]
                offset = view['byteOffset']
                self.assertEqual(binary[offset:offset+view['byteLength']], (source_dir / source['uri']).read_bytes())
        for name, size in [('stone', 2048), ('wood', 1024), ('metal', 1024)]:
            for role in ['color', 'normal', 'roughness']:
                code, raw, mime = asset_response('/graphics/materials/' + name + '-' + role + '.png')
                self.assertEqual(code, 200)
                import io
                self.assertEqual(Image.open(io.BytesIO(raw)).size, (size, size))

class GraphicsHTTPTests(unittest.TestCase):
    def test_routes_auth_and_existing_actions(self):
        import re
        import threading
        from types import SimpleNamespace
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from unittest.mock import Mock, patch
        from chery_showroom.runtime import server
        app = SimpleNamespace(run_id='test', last_client=0, lock=threading.RLock(), state={}, frame=None, command=Mock())
        with patch('chery_showroom.voice.ShowroomProvider') as provider, patch('chery_showroom.credentials.api_key', return_value=None):
            provider.return_value.configured = False
            http = server(app)
            base = 'http://127.0.0.1:' + str(http.server_port)
            try:
                page = urlopen(base + '/').read().decode()
                token = re.search("const token='([^']+)'", page)[1]
                self.assertIn('id="showroom3d"', page)
                self.assertEqual(urlopen(base + '/web/').status, 200)
                for path in ['/graphics/layout.json', '/graphics/signage-font.json', '/web/premium-assets.json', '/web/realism-assets.json', '/web/daylight-assets.json']:
                    with self.subTest(path=path), urlopen(base + path) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers.get_content_type(), 'application/json')
                        self.assertEqual(json.load(response), json.loads(asset_response(path)[1]))
                self.assertEqual(urlopen(base + '/favicon.ico').status, 204)
                self.assertEqual(app.last_client, 0, 'Static files must not maintain the control heartbeat')
                for path in ['/state', '/frame']:
                    with self.assertRaises(HTTPError) as error: urlopen(base + path)
                    self.assertEqual(error.exception.code, 403)
                state = urlopen(Request(base + '/state', headers={'X-Showroom-Token':token}))
                self.assertEqual(state.status, 200)
                state_data=json.load(state)
                self.assertFalse(state_data['camera_ready'])
                self.assertTrue(state_data['reception_available'])
                app.frame = b'jpeg-test'
                ready = urlopen(Request(base + '/state', headers={'X-Showroom-Token':token}))
                self.assertTrue(json.load(ready)['camera_ready'])
                frame = urlopen(Request(base + '/frame', headers={'X-Showroom-Token':token}))
                self.assertEqual(frame.read(), app.frame)
                self.assertGreater(app.last_client, 0)
                body = json.dumps({'action':'stop','run_id':'test'}).encode()
                reply = urlopen(Request(base + '/action', data=body, headers={'X-Showroom-Token':token,'Content-Type':'application/json'}))
                self.assertEqual(reply.status, 202)
                app.command.assert_called_once_with({'action':'stop','run_id':'test'})
            finally:
                http.shutdown(); http.server_close(); http.close_sessions()

class RealismAssetsTests(unittest.TestCase):
    def test_pinned_photographic_assets_and_employee(self):
        import hashlib
        import io
        import struct
        from PIL import Image
        from chery_showroom.web_assets import DIST, ROOT
        manifest = json.loads((DIST / 'realism-assets.json').read_text())
        self.assertEqual(len(manifest), 8)
        for item in manifest:
            raw = (DIST / item['destination']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['output_sha256'])
            self.assertEqual(item['license'], 'CC0-1.0')
            if item['destination'].endswith('.jpg'):
                name = item['destination'].split('/')[-1]
                self.assertEqual(asset_response('/graphics/materials/' + name)[0], 200)
                size = Image.open(io.BytesIO(raw)).size
                self.assertEqual(size, (2048, 2048) if name.startswith('marble') else (1024, 1024))
        code, raw, mime = asset_response('/graphics/staff/receptionist.glb')
        self.assertEqual(code, 200); self.assertEqual(raw[:4], b'glTF')
        length = struct.unpack_from('<I', raw, 12)[0]
        doc = json.loads(raw[20:20+length]); binary = raw[28+length:]
        self.assertGreaterEqual(len(doc['meshes']), 8)
        triangles = sum(doc['accessors'][p['indices']]['count']//3 for mesh in doc['meshes'] for p in mesh['primitives'])
        self.assertGreater(triangles, 100000)
        self.assertTrue(all('uri' not in buffer for buffer in doc['buffers']))
        for image in doc['images']:
            self.assertNotIn('uri', image)
            view = doc['bufferViews'][image['bufferView']]; offset = view.get('byteOffset', 0)
            self.assertLessEqual(max(Image.open(io.BytesIO(binary[offset:offset+view['byteLength']])).size), 1024)
        # When source downloads are present, prove mesh definitions and material values are preserved.
        original = ROOT / 'assets' / 'realism' / 'source' / 'receptionist-original.glb'
        if original.exists():
            source = original.read_bytes(); size = struct.unpack_from('<I', source, 12)[0]
            source_doc = json.loads(source[20:20+size])
            self.assertEqual(doc['meshes'], source_doc['meshes'])
            self.assertEqual(doc['materials'], source_doc['materials'])
        self.assertEqual(asset_response('/graphics/daylight.hdr')[0], 200)
        self.assertEqual(asset_response('/graphics/signage-font.json')[0], 200)
        self.assertEqual(asset_response('/graphics/staff/../../runtime.py')[0], 404)
        self.assertEqual(asset_response('/graphics/staff/unlisted.glb')[0], 404)

class DaylightAssetsTests(unittest.TestCase):
    def test_derived_limestone_integrity_scale_and_routes(self):
        import hashlib
        import io
        from PIL import Image, ImageStat
        from chery_showroom.web_assets import DIST
        manifest = json.loads((DIST / 'daylight-assets.json').read_text())
        self.assertEqual(len(manifest), 6)
        for item in manifest:
            with self.subTest(asset=item['destination']):
                name = item['destination'].split('/')[-1]
                status, raw, mime = asset_response('/graphics/materials/' + name)
                self.assertEqual(status, 200)
                self.assertEqual(mime, 'image/jpeg')
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
                image = Image.open(io.BytesIO(raw))
                self.assertEqual(image.size, (2048, 2048) if name.startswith('limestone-floor') else (1024, 1024))
                self.assertEqual(item['license'], 'CC0-1.0')
                for source, expected in item['source_hashes'].items():
                    self.assertEqual(hashlib.sha256((DIST / source).read_bytes()).hexdigest(), expected)
                if name.endswith('color.jpg'):
                    channels = ImageStat.Stat(image).mean
                    self.assertLess(max(channels) - min(channels), 12, 'Neutral limestone must not inherit the yellow source tint')
        for path in ['/graphics/materials/limestone-source.jpg', '/graphics/materials/../runtime.py', '/graphics/materials/limestone-floor-unknown.jpg']:
            self.assertEqual(asset_response(path)[0], 404)
