"""Reproducible web GLB packaging and original procedural PBR textures.
Run with the project's Python environment; no downloads or source modifications.
"""
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from PIL import Image

WEB = Path(__file__).resolve().parent
SOURCE = WEB.parent / 'assets' / 'furnishings'
PUBLIC = WEB / 'public'


def package_model(item):
    directory = SOURCE / item['name']
    for entry in item['files']:
        data = (directory / entry['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Source hash mismatch: ' + entry['file'])
    doc = json.loads((directory / (item['name'] + '.gltf')).read_text())
    binary = bytearray()
    offsets = []
    for buffer in doc['buffers']:
        binary.extend(b'\0' * (-len(binary) % 4))
        offsets.append(len(binary))
        binary.extend((directory / buffer['uri']).read_bytes())
    for view in doc['bufferViews']:
        view['byteOffset'] = offsets[view['buffer']] + view.get('byteOffset', 0)
        view['buffer'] = 0
    for image in doc.get('images', []):
        binary.extend(b'\0' * (-len(binary) % 4))
        data = (directory / image.pop('uri')).read_bytes()
        image['bufferView'] = len(doc['bufferViews'])
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)})
        binary.extend(data)
    doc['buffers'] = [{'byteLength': len(binary)}]
    doc.setdefault('asset', {})['copyright'] = item['author'] + ' / Poly Haven / CC0-1.0'
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    glb = struct.pack('<III', 0x46546C67, 2, 28 + len(encoded) + len(binary))
    glb += struct.pack('<II', len(encoded), 0x4E4F534A) + encoded
    glb += struct.pack('<II', len(binary), 0x004E4942) + binary
    target = PUBLIC / 'models' / (item['name'] + '.glb')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(glb)
    return {'file': str(target.relative_to(PUBLIC)), 'sha256': hashlib.sha256(glb).hexdigest(),
            'source': item['source'], 'author': item['author'], 'license': item['license'],
            'changes': 'Embedded original buffers and JPEG maps into GLB; no geometry or texture resampling.'}


def texture_set(name, size, seed):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    noise = rng.normal(0, 1, (size, size)).astype(np.float32)
    if name == 'stone':
        grout = (np.minimum(x, 1-x) < .0018) | (np.minimum(y, 1-y) < .0018)
        height = .003 * noise + .002 * np.sin(2*np.pi*(x*3 + y*2))
        height[grout] -= .08
        value = 1 + .008*noise + .0035*np.sin(2*np.pi*(x*3+y*2))
        value[grout] *= .78
        base, rough, strength = [174, 171, 161], .54, 1.3
    elif name == 'wood':
        grain = .55*np.sin(2*np.pi*(x*19 + .15*np.sin(y*2*np.pi))) + .2*np.sin(2*np.pi*(x*71 + .4*np.sin(y*4*np.pi))) + .15*np.sin(2*np.pi*(x*137 + .3*np.sin(y*6*np.pi)))
        height = .0015*grain + .0005*noise
        value = 1 + .035*grain + .012*noise
        base, rough, strength = [111, 80, 53], .61, .8
    else:
        grain = np.sin(2*np.pi*x*230)
        height = .001*grain + .0002*noise
        value = 1 + .012*grain + .006*noise
        base, rough, strength = [142, 151, 155], .33, .45
    color = np.clip(np.array(base)[None, None, :]*value[:, :, None], 0, 255).astype('uint8')
    dx = (np.roll(height, -1, 1)-np.roll(height, 1, 1))*strength
    dy = (np.roll(height, -1, 0)-np.roll(height, 1, 0))*strength
    normal = np.stack([-dx, dy, np.ones_like(dx)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    normal = np.clip((normal*.5+.5)*255, 0, 255).astype('uint8')
    roughness = np.clip((rough + noise*.015)*255, 0, 255).astype('uint8')
    destination = PUBLIC / 'materials'; destination.mkdir(exist_ok=True)
    for role, data in [('color', color), ('normal', normal), ('roughness', roughness)]:
        Image.fromarray(data).save(destination / (name + '-' + role + '.png'), optimize=True)


def main():
    manifest = [package_model(item) for item in json.loads((SOURCE / 'provenance.json').read_text())]
    (PUBLIC / 'premium-assets.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for name, size, seed in [('stone', 2048, 41), ('wood', 1024, 42), ('metal', 1024, 43)]:
        texture_set(name, size, seed)
    print('Verified sources; packed 2 GLBs and generated 9 original PBR maps.')

if __name__ == '__main__':
    main()
