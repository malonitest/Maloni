"""Static-world A* navigation with a reserved 1.5 m diameter corridor."""
import heapq,math
import numpy as np
CLEARANCE=.75
RESOLUTION=.25

class Navigator:
    def __init__(self,model=None,*,obstacles=None,bounds=None,clearance=CLEARANCE):
        self.model=model;self.obstacles=[];self.clearance=clearance
        if model is None:
            self.obstacles=[(np.asarray(lo),np.asarray(hi)) for lo,hi in (obstacles or [])]
            self.bounds=np.asarray(bounds if bounds is not None else [[-8.1,-5.2],[8.1,6.2]])
            return
        import mujoco
        data=mujoco.MjData(model);mujoco.mj_forward(model,data)
        for i in range(model.ngeom):
            if model.geom_bodyid[i]!=0 or not (model.geom_contype[i] or model.geom_conaffinity[i]):continue
            size=model.geom_size[i];pos=data.geom_xpos[i]
            if model.geom_type[i]==mujoco.mjtGeom.mjGEOM_PLANE:continue
            if model.geom_type[i]==mujoco.mjtGeom.mjGEOM_BOX:
                half=np.abs(data.geom_xmat[i].reshape(3,3))@size
            elif model.geom_type[i]==mujoco.mjtGeom.mjGEOM_CYLINDER:half=np.array([size[0],size[0],size[1]])
            else:raise ValueError('Unsupported static collision geometry: '+(model.geom(i).name or str(i)))
            if pos[2]+half[2]<.12:continue  # the single floor slab is not a wall
            self.obstacles.append((pos[:2]-half[:2],pos[:2]+half[:2]))
        self.bounds=np.array([[-8.1,-5.2],[8.1,6.2]])
    def _obstacle_arrays(self):
        if getattr(self,'_cached_key',None)!=(len(self.obstacles),self.clearance):
            self._cached_key=(len(self.obstacles),self.clearance)
            self._lows=np.array([lo for lo,hi in self.obstacles]).reshape(-1,2)-self.clearance
            self._highs=np.array([hi for lo,hi in self.obstacles]).reshape(-1,2)+self.clearance
        return self._lows,self._highs
    def free(self,point):
        p=np.asarray(point,dtype=float)
        if p.shape!=(2,) or not np.isfinite(p).all() or np.any(p<self.bounds[0]) or np.any(p>self.bounds[1]):return False
        low,high=self._obstacle_arrays()
        return not bool(np.any(np.all((p>=low)&(p<=high),axis=1)))
    def segment_free(self,start,end):
        start=np.asarray(start,dtype=float);end=np.asarray(end,dtype=float)
        if start.shape!=(2,) or end.shape!=(2,) or not np.isfinite([start,end]).all():return False
        # Continuous slab intersection: sampling misses a tangent at a padded
        # furniture corner and can strand the customer partway through a route.
        if np.any(np.minimum(start,end)<self.bounds[0]) or np.any(np.maximum(start,end)>self.bounds[1]):return False
        low,high=self._obstacle_arrays()
        if not len(low):return True
        low=low-1e-9;high=high+1e-9
        delta=end-start;moving=np.abs(delta)>1e-14
        parallel_outside=np.any((~moving)&((start<low)|(start>high)),axis=1)
        denom=np.where(moving,delta,1.)
        a=(low-start)/denom;b=(high-start)/denom
        near=np.where(moving,np.minimum(a,b),-np.inf).max(axis=1)
        far=np.where(moving,np.maximum(a,b),np.inf).min(axis=1)
        return not bool(np.any((~parallel_outside)&(np.maximum(near,0)<=np.minimum(far,1))))
    def route(self,start,target,*,allow_recovery=False):
        self.last_recovery=False
        start=np.asarray(start,dtype=float);target=np.asarray(target,dtype=float)
        if not self.free(target):raise ValueError('Navigation target lacks the reserved corridor clearance.')
        if not self.free(start):
            # After braking, small balance drift can leave the robot inside the
            # planning margin while still outside the physical obstacle. Admit
            # only a bounded escape, never a path through an occupied object.
            tight=Navigator(obstacles=self.obstacles,bounds=self.bounds,clearance=max(0.,self.clearance-.10))
            comfortable=Navigator(obstacles=self.obstacles,bounds=self.bounds,clearance=self.clearance+.15)
            if allow_recovery and tight.free(start):
                candidates=[]
                for radius in (.25,.35,.5):
                    for angle in np.linspace(0,2*math.pi,16,endpoint=False):
                        point=start+radius*np.array([math.cos(angle),math.sin(angle)])
                        if comfortable.free(point) and tight.segment_free(start,point):
                            candidates.append((radius+.1*np.linalg.norm(target-point),point))
                for _,point in sorted(candidates,key=lambda x:x[0]):
                    try:tail=self.route(point,target)
                    except ValueError:continue
                    self.last_recovery=True
                    return [tuple(point),*tail]
            raise ValueError('Navigation start lacks clearance for a safe recovery.')
        if self.segment_free(start,target):return [tuple(target)]
        origin=self.bounds[0]
        def coordinate(node):return origin+np.array(node)*RESOLUTION
        def nearest(p):
            base=np.rint((p-origin)/RESOLUTION).astype(int)
            candidates=[tuple(base+[dx,dy]) for dx in range(-2,3) for dy in range(-2,3)]
            candidates=[n for n in candidates if self.segment_free(p,coordinate(n))]
            if not candidates:raise ValueError('Cannot connect endpoint to the navigation grid.')
            return min(candidates,key=lambda n:np.linalg.norm(coordinate(n)-p))
        first,last=nearest(start),nearest(target);cost={first:0.};parent={};pending=[(0.,first)]
        while pending:
            _,node=heapq.heappop(pending)
            if node==last:break
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt=node[0]+dx,node[1]+dy
                if not self.segment_free(coordinate(node),coordinate(nxt)):continue
                value=cost[node]+math.hypot(dx,dy)
                if value>=cost.get(nxt,float('inf')):continue
                cost[nxt]=value;parent[nxt]=node
                heapq.heappush(pending,(value+math.dist(nxt,last),nxt))
        else:raise ValueError('No route with the reserved corridor clearance.')
        nodes=[last]
        while nodes[-1]!=first:nodes.append(parent[nodes[-1]])
        points=[start,*[coordinate(n) for n in reversed(nodes)],target];result=[];i=0
        while i<len(points)-1:
            j=len(points)-1
            while j>i+1 and not self.segment_free(points[i],points[j]):j-=1
            result.append(tuple(points[j]));i=j
        return result
