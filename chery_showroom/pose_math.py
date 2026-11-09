"""Quaternion utilities for the existing showroom controllers, independent of MuJoCo."""
import numpy as np

def matrix_quaternion(matrix):
    m=np.asarray(matrix,dtype=float).reshape(3,3)
    # Symmetric eigenproblem avoids numerical cancellation near half turns.
    k=np.array([[m[0,0]-m[1,1]-m[2,2],m[0,1]+m[1,0],m[0,2]+m[2,0],m[2,1]-m[1,2]],
        [m[0,1]+m[1,0],m[1,1]-m[0,0]-m[2,2],m[1,2]+m[2,1],m[0,2]-m[2,0]],
        [m[0,2]+m[2,0],m[1,2]+m[2,1],m[2,2]-m[0,0]-m[1,1],m[1,0]-m[0,1]],
        [m[2,1]-m[1,2],m[0,2]-m[2,0],m[1,0]-m[0,1],np.trace(m)]])/3
    _,vectors=np.linalg.eigh(k);x,y,z,w=vectors[:,-1];q=np.array([w,x,y,z])
    return q if q[0]>=0 else -q

def multiply(a,b):
    w,x,y,z=a;v,i,j,k=b
    return np.array([w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v])

def forward(sim):
    if hasattr(sim,'forward'):sim.forward()
    else:
        import mujoco
        mujoco.mj_forward(sim.model,sim.data)

def camera_sync(model,data):
    if not getattr(model,'native',False):
        import mujoco
        mujoco.mj_camlight(model,data)
