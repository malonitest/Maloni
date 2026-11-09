"""Deterministic CC0 marble derivatives. No downloads; preserves original assets.
Run after prepare_realism.py. Floor: 4x4 atlas, 2K. Wall: 1K.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

WEB = Path(__file__).resolve().parent
PUBLIC = WEB / 'public'


def prepare():
    sources = json.loads((PUBLIC / 'realism-assets.json').read_text())
    marble = [item for item in sources if item['destination'].startswith('materials/marble-')]
    if len(marble) != 3:
        raise ValueError('Run prepare_realism.py first')
    inputs = {}
    for item in marble:
        raw = (PUBLIC / item['destination']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['output_sha256']:
            raise ValueError('Marble source checksum mismatch')
        role = Path(item['destination']).stem.split('-')[-1]
        inputs[role] = Image.open(PUBLIC / item['destination']).convert('RGB')
    source = np.asarray(inputs['color'], dtype=np.float32)
    luminance = source @ np.array([.2126, .7152, .0722], dtype=np.float32)
    # Suppress source brick colour while retaining its fine natural mineral structure.
    mineral = np.clip((luminance - luminance.mean()) * .16, -8, 8)
    base = np.array([215, 214, 207], dtype=np.float32)
    neutral = Image.fromarray(np.clip(base + mineral[..., None], 0, 255).astype('uint8'))
    rough = np.asarray(inputs['roughness'], dtype=np.float32).mean(axis=2)
    rough = Image.fromarray(np.clip(193 + (rough - rough.mean()) * .12, 180, 204).astype('uint8')).convert('RGB')
    images = {'color': neutral, 'normal': inputs['normal'], 'roughness': rough}
    result = []
    for role, image in images.items():
        for name, size in [('limestone-wall', 1024), ('limestone-floor', 2048)]:
            if name.endswith('floor'):
                # 16 small deterministic tone/offset variants, with a two-pixel atlas gutter.
                atlas = Image.new('RGB', (size, size))
                tile = image.resize((508, 508), Image.Resampling.LANCZOS)
                pixels = np.asarray(tile)
                for index in range(16):
                    variant = np.roll(pixels, ((index * 137) % 508, (index * 79) % 508), axis=(0, 1))
                    if role == 'color':
                        variant = np.clip(variant.astype('float32') + (index % 5 - 2) * .7, 0, 255).astype('uint8')
                    padded = np.pad(variant, ((2, 2), (2, 2), (0, 0)), mode='edge')
                    atlas.paste(Image.fromarray(padded), ((index % 4) * 512, (index // 4) * 512))
                output = atlas
            else:
                output = image.resize((size, size), Image.Resampling.LANCZOS)
            destination = 'materials/' + name + '-' + role + '.jpg'
            path = PUBLIC / destination
            output.save(path, quality=94, subsampling=0, optimize=True)
            result.append(dict(destination=destination, size=[size, size], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               license='CC0-1.0', source='https://polyhaven.com/a/marble_01',
                               author='Rob Tuytel / Poly Haven; MALONI colour/atlas derivative',
                               source_hashes={item['destination']: item['output_sha256'] for item in marble}))
    (PUBLIC / 'daylight-assets.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Prepared six pinned limestone derivatives')


if __name__ == '__main__':
    prepare()
