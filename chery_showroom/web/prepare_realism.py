"""Restore pinned CC0 realism assets and prepare their self-contained web versions.
Only --restore downloads missing sources; original meshes/UVs/materials stay intact.
"""
import argparse
import hashlib
import io
import json
import shutil
import struct
import urllib.request
from pathlib import Path
from PIL import Image

WEB = Path(__file__).resolve().parent
BASE = WEB.parent / 'assets' / 'realism'
PUBLIC = WEB / 'public'


def optimize_employee(raw):
    size = struct.unpack_from('<I', raw, 12)[0]
    doc = json.loads(raw[20:20+size])
    binary = raw[28+size:]
    output = bytearray()
    # Preserve geometry, accessors, indices and all material values byte-for-byte.
    for view in doc['bufferViews']:
        data = binary[view.get('byteOffset', 0):view.get('byteOffset', 0)+view['byteLength']]
        output.extend(b'\0' * (-len(output) % 4))
        view['byteOffset'] = len(output); output.extend(data)
    for image in doc['images']:
        view = doc['bufferViews'][image['bufferView']]
        source = bytes(output[view['byteOffset']:view['byteOffset']+view['byteLength']])
        picture = Image.open(io.BytesIO(source)); picture.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        alpha = 'A' in picture.getbands() and picture.getchannel('A').getextrema()[0] < 255
        encoded = io.BytesIO()
        if alpha:
            picture.save(encoded, format='PNG', optimize=True); mime='image/png'
        else:
            picture.convert('RGB').save(encoded, format='JPEG', quality=90, optimize=True); mime='image/jpeg'
        output.extend(b'\0' * (-len(output) % 4))
        image['bufferView'] = len(doc['bufferViews']); image['mimeType'] = mime
        doc['bufferViews'].append(dict(buffer=0, byteOffset=len(output), byteLength=len(encoded.getvalue())))
        output.extend(encoded.getvalue())
    # Old image buffers are deliberately preserved so buffer-view sharing remains valid.
    # Compact by copying only referenced views, removing orphaned source images.
    image_views = {image['bufferView'] for image in doc['images']}
    referenced = image_views | {a['bufferView'] for a in doc['accessors'] if 'bufferView' in a}
    for accessor in doc['accessors']:
        for sparse in accessor.get('sparse', {}).values():
            if isinstance(sparse, dict) and 'bufferView' in sparse: referenced.add(sparse['bufferView'])
    compact = bytearray(); remap={}; views=[]
    for index in sorted(referenced):
        view = doc['bufferViews'][index].copy(); data=output[view['byteOffset']:view['byteOffset']+view['byteLength']]
        compact.extend(b'\0' * (-len(compact) % 4)); view['byteOffset']=len(compact); compact.extend(data)
        remap[index]=len(views); views.append(view)
    for accessor in doc['accessors']:
        if 'bufferView' in accessor: accessor['bufferView']=remap[accessor['bufferView']]
        for sparse in accessor.get('sparse', {}).values():
            if isinstance(sparse, dict) and 'bufferView' in sparse: sparse['bufferView']=remap[sparse['bufferView']]
    for image in doc['images']: image['bufferView']=remap[image['bufferView']]
    doc['bufferViews']=views; doc['buffers']=[{'byteLength':len(compact)}]
    doc['asset']['copyright']='Innerscene / MakeHuman CC0; textures resized to 1K for MALONI showroom'
    encoded=json.dumps(doc,separators=(',',':')).encode(); encoded+=b' '*(-len(encoded)%4)
    compact.extend(b'\0' * (-len(compact) % 4))
    return struct.pack('<III',0x46546c67,2,28+len(encoded)+len(compact))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(compact),0x004e4942)+compact


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--restore',action='store_true'); args=parser.parse_args()
    source_dir=BASE/'source'; source_dir.mkdir(parents=True,exist_ok=True)
    result=[]
    for item in json.loads((BASE/'sources.json').read_text()):
        source=source_dir/item['file']
        if not source.exists() and args.restore:
            req=urllib.request.Request(item['url'],headers={'User-Agent':'MaloniShowroomAssetPreparation/1.0'})
            with urllib.request.urlopen(req,timeout=120) as response: data=response.read()
            source.write_bytes(data)
        data=source.read_bytes()
        key='sha256' if 'sha256' in item else 'md5'
        if hashlib.new(key,data).hexdigest()!=item[key]: raise ValueError('Source checksum mismatch: '+item['file'])
        target=PUBLIC/item['destination']; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(optimize_employee(data) if item['file']=='receptionist-original.glb' else data)
        result.append({**item,'source_sha256':hashlib.sha256(data).hexdigest(),'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                       'changes':'Textures resized to 1K; geometry and PBR materials preserved' if item['file']=='receptionist-original.glb' else 'Original bytes'})
        print(item['destination'],target.stat().st_size,flush=True)
    shutil.copyfile(WEB/'node_modules/three/examples/fonts/helvetiker_regular.typeface.json',PUBLIC/'signage-font.json')
    font = json.loads((PUBLIC/'signage-font.json').read_text())
    (PUBLIC/'FONT_LICENSE.txt').write_text(font['original_font_information']['license_description'] + '\n')
    (PUBLIC/'realism-assets.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__': main()
