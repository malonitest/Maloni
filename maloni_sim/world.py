"""Validated Python bindings for the local C++ engine (ctypes, no Python ABI coupling)."""
import ctypes as C
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PTR = C.POINTER(C.c_double)

def array(value, shape):
    a = np.ascontiguousarray(value, dtype=np.float64)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'Expected finite array of shape {shape}, got {a.shape}')
    return a

def pointer(a):
    return a.ctypes.data_as(PTR)

def library():
    path = ROOT/'build/maloni_sim/libmaloni_physics.so'
    if not path.is_file():
        raise RuntimeError('Build physics first: bash scripts/build_maloni_sim.sh')
    lib = C.CDLL(str(path))
    lib.ms_error.restype = C.c_char_p
    signatures = {
        'create': ([C.c_double], C.c_void_p), 'destroy': ([C.c_void_p], None),
        'body': ([C.c_void_p,C.c_int,C.c_int,PTR], C.c_int),
        'init': ([C.c_void_p],C.c_int), 'reset': ([C.c_void_p],C.c_int),
        'shape': ([C.c_void_p,C.c_int,C.c_int,PTR,C.c_double,C.c_double],C.c_int),
        'cylinder': ([C.c_void_p,C.c_int,PTR,PTR,C.c_double,C.c_double,C.c_double],C.c_int),
        'set': ([C.c_void_p,PTR,PTR],C.c_int), 'get': ([C.c_void_p,PTR,PTR],C.c_int),
        'step': ([C.c_void_p,PTR,C.c_int],C.c_int),
        'pose': ([C.c_void_p,C.c_int,PTR],C.c_int),
        'jac': ([C.c_void_p,C.c_int,PTR,PTR],C.c_int),
        'force': ([C.c_void_p,C.c_int,PTR,PTR,PTR],C.c_int),
        'options': ([C.c_void_p,PTR,C.c_int,C.c_int],C.c_int),
        'contacts': ([C.c_void_p,PTR,C.c_int],C.c_int),
        'body_contacts': ([C.c_void_p,C.c_int],C.c_int),
        'fixed_base': ([C.c_void_p,C.c_int],C.c_int),
        'energy': ([C.c_void_p,PTR],C.c_int),
        'diagnostics': ([C.c_void_p,PTR],None),
        'profile': ([C.c_void_p,PTR],None),
    }
    for name,(args,result) in signatures.items():
        fn=getattr(lib,'ms_'+name); fn.argtypes=args; fn.restype=result
    return lib

class World:
    """One free-root tree, world-frame velocities; quaternions use w,x,y,z.

    Version 1 supports plane and convex body contacts within one free-root tree. Unsupported scene capabilities fail
    at load rather than silently becoming non-colliding geometry.
    """
    def __init__(self, scene):
        self._handle = None
        if isinstance(scene,(str,Path)):
            scene=json.loads(Path(scene).read_text())
        self.scene=scene
        if scene.get('version') != 1:
            raise ValueError('Expected MALONI scene version 1')
        capabilities=scene.get('requires',[])
        unsupported=set(capabilities)-{'articulated_tree','plane_contacts','body_contacts'}
        if unsupported: raise NotImplementedError(f'Unsupported capabilities: {sorted(unsupported)}')
        if scene.get('static_colliders') and 'body_contacts' not in capabilities:raise ValueError('Static colliders require body_contacts')
        self.dt=float(scene.get('timestep',0.002))
        if not math.isfinite(self.dt) or self.dt<=0: raise ValueError('Invalid timestep')
        self.bodies=scene.get('bodies',[])
        if not self.bodies: raise ValueError('Scene needs a free-root body')
        self.names=[b['name'] for b in self.bodies]
        if len(set(self.names))!=len(self.names): raise ValueError('Duplicate body names')
        self.joint_names=[b['joint']['name'] for b in self.bodies if b.get('joint')]
        if len(set(self.joint_names))!=len(self.joint_names): raise ValueError('Duplicate joints')
        self.nj=len(self.joint_names)
        self.lib=library();self._handle=self.lib.ms_create(self.dt)
        if not self._handle: raise RuntimeError(self.lib.ms_error().decode())
        try:
            for i,b in enumerate(self.bodies):
                parent=b.get('parent',-1)
                if not isinstance(parent,int) or parent>=i or parent< -1 or (i>0 and parent<0):
                    raise ValueError('Bodies must form one parent-first tree')
                j=b.get('joint',{})
                if j.get('type','hinge')!='hinge': raise NotImplementedError('Only hinge joints supported')
                if i==0 and j: raise ValueError('Root must be free, not hinged')
                inertia=array(b['inertia'],(3,3))
                if not np.allclose(inertia,inertia.T) or np.linalg.eigvalsh(inertia).min()<=0:
                    raise ValueError('Body inertia must be symmetric positive definite')
                axis=array(j.get('axis',[0,0,1]),(3,))
                if np.linalg.norm(axis)<1e-12: raise ValueError('Zero hinge axis')
                rest=array(b.get('quaternion',[1,0,0,0]),(4,))
                if np.linalg.norm(rest)<1e-12: raise ValueError('Zero body quaternion')
                params=[b['mass'],*b.get('offset',[0,0,0]),*rest,*b.get('com',[0,0,0]),
                    *inertia.ravel(),*axis,j.get('damping',0),j.get('friction',0),j.get('armature',0),
                    *j.get('range',[-1e30,1e30]),j.get('effort',1e30)]
                p=array(params,(29,))
                if p[0]<=0 or min(p[23:26])<0 or p[28]<=0: raise ValueError('Invalid mass or joint parameters')
                self._call('body',parent,int(bool(j)),pointer(p))
            self._call('init')
            for i,b in [*enumerate(self.bodies),(-1,{'colliders':scene.get('static_colliders',[])})]:
                for s in b.get('colliders',[]):
                    if s.get('type')=='cylinder':
                        center=array(s['center'],(3,));axis=array(s['axis'],(3,))
                        radius=float(s['radius']);half=float(s['half_length']);mu=float(s.get('friction',.6))
                        if not math.isfinite(radius+half+mu) or min(radius,half)<=0 or mu<0 or np.linalg.norm(axis)<1e-12: raise ValueError('Invalid cylinder')
                        self._call('cylinder',i,pointer(center),pointer(axis),radius,half,mu)
                        continue
                    if set(s)-{'points','radius','friction'}: raise ValueError('Unknown collider fields')
                    points=np.ascontiguousarray(s['points'],dtype=float)
                    if points.ndim!=2 or points.shape[1]!=3 or not len(points) or not np.isfinite(points).all():
                        raise ValueError('Collider points must be finite Nx3')
                    radius=float(s.get('radius',0));mu=float(s.get('friction',0.6))
                    if not math.isfinite(radius+mu) or min(radius,mu)<0: raise ValueError('Invalid collider')
                    self._call('shape',i,len(points),pointer(points),radius,mu)
            gravity=array(scene.get('gravity',[0,0,-9.81]),(3,))
            iterations=scene.get('solver_iterations',60)
            if not isinstance(iterations,int) or not 1<=iterations<=10000: raise ValueError('Invalid iteration count')
            self._call('fixed_base',int(scene.get('fixed_base',False)))
            self._call('body_contacts',int('body_contacts' in capabilities))
            self._call('options',pointer(gravity),int(scene.get('ground',True)),iterations)
            q=np.zeros(7+self.nj);q[:3]=scene.get('position',[0,0,1]);q[3:7]=scene.get('orientation',[1,0,0,0]);q[7:]=scene.get('joint_positions',[0]*self.nj)
            self._initial=(q.copy(),np.zeros(6+self.nj));self.reset()
        except Exception:
            self.close();raise

    def _call(self,name,*args):
        if not self._handle: raise RuntimeError('World is closed')
        result=getattr(self.lib,'ms_'+name)(self._handle,*args)
        if result<0: raise RuntimeError(self.lib.ms_error().decode())
        return result

    def reset(self):
        self._call('reset');self.set_state(*self._initial)

    def set_state(self,q,v):
        q=array(q,(7+self.nj,));v=array(v,(6+self.nj,))
        norm=np.linalg.norm(q[3:7])
        if norm<1e-12: raise ValueError('Zero base quaternion')
        q=q.copy();q[3:7]/=norm
        self._call('set',pointer(q),pointer(v))

    def state(self):
        q=np.empty(7+self.nj);v=np.empty(6+self.nj)
        self._call('get',pointer(q),pointer(v));return q,v

    def step(self,moments=None,count=1):
        if not isinstance(count,int) or not 1<=count<=100000: raise ValueError('Invalid step count')
        moments=array(np.zeros(self.nj) if moments is None else moments,(self.nj,))
        self._call('step',pointer(moments),count)

    def body_id(self,body):
        i=self.names.index(body) if isinstance(body,str) else body
        if not isinstance(i,int) or not 0<=i<len(self.bodies): raise ValueError('Invalid body id')
        return i

    def pose(self,body=0):
        result=np.empty(7);self._call('pose',self.body_id(body),pointer(result));return result

    def jacobian(self,body=0,point=(0,0,0)):
        p=array(point,(3,));j=np.empty((3,6+self.nj))
        self._call('jac',self.body_id(body),pointer(p),pointer(j));return j

    def apply_force(self,body,force,point=(0,0,0),torque=(0,0,0)):
        """One-step world force/torque at a body-local point; forces clear each substep."""
        values=[array(x,(3,)) for x in (point,force,torque)]
        self._call('force',self.body_id(body),*(pointer(x) for x in values))

    def contacts(self):
        n=self._call('contacts',pointer(np.empty((0,13))),0)
        rows=np.empty((n,13));self._call('contacts',pointer(rows),n)
        return [dict(body=int(r[0]),point=r[1:4].tolist(),depth=r[4],normal_impulse=r[5],
                     tangent_impulse=r[6:8].tolist(),friction=r[8],other_body=int(r[9]),normal=r[10:13].tolist()) for r in rows]

    def energy(self):
        out=np.empty(2);self._call('energy',pointer(out))
        return dict(kinetic=out[0],potential=out[1],total=float(out.sum()))

    def profile(self):
        if not self._handle:raise RuntimeError('World is closed')
        out=np.empty(4);self.lib.ms_profile(self._handle,pointer(out))
        return dict(zip(('kinematics','dynamics','collision','solver'),map(float,out)))

    def diagnostics(self):
        out=np.empty(3)
        if not self._handle: raise RuntimeError('World is closed')
        self.lib.ms_diagnostics(self._handle,pointer(out))
        return dict(sim_time=float(out[0]),max_penetration=float(out[1]),normal_residual=float(out[2]))

    def close(self):
        if self._handle: self.lib.ms_destroy(self._handle);self._handle=None
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def __del__(self): self.close()
