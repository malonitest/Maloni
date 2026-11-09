"""Decode pinned, locally stored CC-BY GLBs and bake their materials for MuJoCo."""
import json,struct,io
from pathlib import Path
import numpy as np,meshoptimizer,trimesh

def unpack(path):
 raw=Path(path).read_bytes();length,_=struct.unpack_from('<II',raw,12);doc=json.loads(raw[20:20+length]);offset=20+length;blen,_=struct.unpack_from('<II',raw,offset);binary=raw[offset+8:offset+8+blen];out=bytearray()
 for view in doc['bufferViews']:
  ext=view.get('extensions',{}).pop('EXT_meshopt_compression',None)
  if ext:
   chunk=binary[ext.get('byteOffset',0):ext.get('byteOffset',0)+ext['byteLength']];mode=ext['mode'];count=ext['count'];stride=ext['byteStride']
   if mode=='TRIANGLES':decoded=meshoptimizer.decode_index_buffer(count,stride,chunk)
   elif mode=='INDICES':decoded=meshoptimizer.decode_index_sequence(count,stride,chunk)
   else:decoded=meshoptimizer.decode_vertex_buffer(count,stride,chunk)
   filter=ext.get('filter','NONE')
   if filter!='NONE':decoded=getattr(meshoptimizer,{'OCTAHEDRAL':'decode_filter_oct','QUATERNION':'decode_filter_quat','EXPONENTIAL':'decode_filter_exp'}[filter])(decoded,count,stride)
   data=decoded.tobytes()
   if mode in ('TRIANGLES','INDICES'):data=decoded.tobytes()[:count*stride]
   if len(data)!=view['byteLength']:raise ValueError((len(data),view['byteLength'],ext))
  else:data=binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
  while len(out)%4:out.append(0)
  view['buffer']=0;view['byteOffset']=len(out);out.extend(data)
  if not view.get('extensions'):view.pop('extensions',None)
 # trimesh does not normalize integer POSITION accessors; resolve them before loading.
 positions={p['attributes']['POSITION'] for m in doc['meshes'] for p in m['primitives']}
 for index in positions:
  accessor=doc['accessors'][index]
  if accessor['componentType']==5126:continue
  dtype=np.dtype({5120:'i1',5121:'u1',5122:'<i2',5123:'<u2'}[accessor['componentType']])
  view=doc['bufferViews'][accessor['bufferView']]
  values=np.ndarray((accessor['count'],3),dtype=dtype,buffer=bytes(out),offset=view['byteOffset']+accessor.get('byteOffset',0),strides=(view.get('byteStride',dtype.itemsize*3),dtype.itemsize)).astype(np.float32)
  if accessor.get('normalized'):values=np.maximum(values/np.iinfo(dtype).max,-1)
  while len(out)%4:out.append(0)
  doc['bufferViews'].append(dict(buffer=0,byteOffset=len(out),byteLength=values.nbytes))
  accessor.update(componentType=5126,normalized=False,bufferView=len(doc['bufferViews'])-1,byteOffset=0,min=values.min(0).tolist(),max=values.max(0).tolist())
  out.extend(values.astype('<f4').tobytes())
 doc['buffers']=[{'byteLength':len(out)}]
 for field in ('extensionsUsed','extensionsRequired'):
  doc[field]=[v for v in doc.get(field,[]) if v!='EXT_meshopt_compression']
 for mesh in doc['meshes']:
  for primitive in mesh['primitives']:
   if 'COLOR_0' in primitive['attributes']:primitive.pop('material',None)
 js=json.dumps(doc).encode();js+=b' '*((-len(js))%4);out+=b'\0'*((-len(out))%4)
 packed=struct.pack('<III',0x46546c67,2,28+len(js)+len(out))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(out),0x004e4942)+out
 return trimesh.load(io.BytesIO(packed),file_type='glb',process=False),doc


SURFACES={
 'paint':dict(specular=.65,shininess=.72,metallic=.35,roughness=.36),
 'glass':dict(specular=.85,shininess=.95,metallic=.05,roughness=.08),
 'chrome':dict(specular=.72,shininess=.8,metallic=.95,roughness=.2),
 'rubber':dict(specular=.08,shininess=.12,metallic=0,roughness=.85),
 'trim':dict(specular=.3,shininess=.4,metallic=.1,roughness=.5),
}

def convert(source, target_length):
    scene,doc=unpack(source)
    directory=Path(source).parent;stem=Path(source).stem
    bounds=scene.bounds;extent=bounds[1]-bounds[0];longest=int(np.argmax(extent))
    rotation=np.array([[0,0,-1],[-1,0,0],[0,1,0]]) if longest==2 else np.array([[1,0,0],[0,0,-1],[0,1,0]])
    transformed=np.array([v@rotation.T for v in trimesh.bounds.corners(bounds)])
    center=(transformed.min(0)+transformed.max(0))/2;center[2]=transformed[:,2].min()
    scale=target_length/max(extent)
    entries=[]
    from PIL import Image
    for index,node in enumerate(scene.graph.nodes_geometry):
        transform,name=scene.graph[node];g=scene.geometry[name].copy();g.apply_transform(transform)
        source_normals=g.vertex_normals.copy()@rotation.T
        source_normals/=np.maximum(np.linalg.norm(source_normals,axis=1,keepdims=True),1e-12)
        g.vertices=(g.vertices@rotation.T-center)*scale
        g.vertex_normals=source_normals
        groups=[('trim',g)]
        if g.visual.kind=='vertex':
            colors=g.visual.vertex_colors[g.faces,:3].mean(axis=1)
            mid=g.triangles_center
            roles=np.full(len(g.faces),'trim',dtype='<U8')
            roles[(colors.max(1)-colors.min(1)<12)&(colors.mean(1)>105)]='chrome'
            roles[(colors[:,2]>colors[:,0]*1.4)&(colors[:,2]>55)]='paint'
            dark=colors.max(1)<30
            roles[dark]='rubber'
            roles[dark&(mid[:,2]>.97)&(np.abs(mid[:,1])<.94)]='glass'
            for role in np.unique(roles):
                if np.sum(roles==role)<4:roles[roles==role]='trim'
            groups=[]
            for role in np.unique(roles):
                indices=np.flatnonzero(roles==role);unique=np.unique(g.faces[indices].reshape(-1))
                part=g.submesh([indices],append=True);part.vertex_normals=source_normals[unique]
                groups.append((role,part))
        for role,g in groups:
            if len(g.faces)<4:continue
            # MuJoCo requires a non-degenerate volume for the mesh hull.
            if np.linalg.matrix_rank(g.vertices-g.vertices.mean(0),tol=1e-8)<3:
                g.vertices[0]+=np.linalg.svd(g.vertices-g.vertices.mean(0))[2][-1]*.00005
            label=f'{stem}_{index}_{role}';material=dict(rgba=[1,1,1,1],**SURFACES[role])
            uv=None;per_face=False
            if g.visual.kind=='vertex':
                colors=np.rint(g.visual.vertex_colors[g.faces,:3].mean(axis=1)).astype(np.uint8)
                if role=='paint':
                    colors[:]=[38,78,97] if stem=='chery-tiggo' else [157,171,176]
                elif role=='glass':colors[:]=[20,30,37]
                elif role=='rubber':colors[:]=[28,29,30]
                palette,inverse=np.unique(colors,axis=0,return_inverse=True)
                side=int(np.ceil(np.sqrt(len(palette))));pixels=np.zeros((side*4,side*4,3),dtype=np.uint8)
                for j,color in enumerate(palette):pixels[(j//side)*4:(j//side+1)*4,(j%side)*4:(j%side+1)*4]=color
                Image.fromarray(pixels).save(directory/(label+'.png'))
                centers=np.column_stack(((inverse%side+.5)/side,1-(inverse//side+.5)/side))
                # Three distinct UVs per face preserve a valid tangent frame in PBR renderers.
                uv=(centers[:,None,:]+np.array([[-.2,-.2],[.2,-.2],[0,.2]])[None,:,:]/side).reshape(-1,2);per_face=True
                material['texture']=label+'.png'
            elif g.visual.kind=='texture':
                m=g.visual.material
                factor=getattr(m,'baseColorFactor',None)
                if factor is not None:
                    material['rgba']=(np.asarray(factor,dtype=float)/255).tolist()
                    if factor[0]>150 and factor[1]<40:material.update(rgba=[.48,.035,.045,1],**SURFACES['paint'])
                    elif factor[3]<200:material.update(rgba=[.1,.16,.19,.65],**SURFACES['glass'])
                image=getattr(m,'baseColorTexture',None)
                if image is not None and g.visual.uv is not None:
                    image.save(directory/(label+'.png'));uv=g.visual.uv;material['texture']=label+'.png'
            if uv is None:
                planar=g.vertices[:,[0,2]]
                uv=(planar-planar.min(0))/np.maximum(np.ptp(planar,axis=0),1e-9)
            normals=g.vertex_normals
            with (directory/(label+'.obj')).open('w') as out:
                for vertex in g.vertices:out.write('v '+' '.join(f'{v:.7f}' for v in vertex)+'\n')
                for normal in normals:out.write('vn '+' '.join(f'{v:.6f}' for v in normal)+'\n')
                if uv is not None:
                    for v in uv:out.write(f'vt {v[0]:.7f} {v[1]:.7f}\n')
                for j,face in enumerate(g.faces):
                    fields=[]
                    for corner,v in enumerate(face):
                        fields.append(f'{v+1}/{3*j+corner+1 if per_face else v+1}/{v+1}' if uv is not None else f'{v+1}//{v+1}')
                    out.write('f '+' '.join(fields)+'\n')
            entries.append(dict(file=label+'.obj',material=material,faces=len(g.faces),surface=role))
    result=dict(parts=entries,bounds=((transformed-center)*scale).tolist(),length=target_length,asset=doc['asset'])
    (directory/(stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    for name,length in [('bmw-x1',4.48),('volvo-xc60',4.69),('chery-tiggo',4.72)]:
        result=convert(Path(__file__).with_name('assets')/'library'/(name+'.glb'),length)
        print(name,len(result['parts']),sum(p['faces'] for p in result['parts']))
