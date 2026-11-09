"""Original metre-scale, stylized adult. Mocap visuals only; no contacts or DOFs."""
import math
import xml.etree.ElementTree as E
import numpy as np

PARTS = ('jacket','hips','shirt','neck','head','hair','nose','eye_l','eye_r',
         'upperarm_l','forearm_l','hand_l','upperarm_r','forearm_r','hand_r',
         'thigh_l','shin_l','shoe_l','thigh_r','shin_r','shoe_r')


def add_actor(world):
    body=E.SubElement(world,'body',name='demo_customer',mocap='true',pos='0 0 -10')
    suit='.075 .12 .18 1';skin='.64 .43 .29 1';trousers='.12 .14 .17 1'
    for name in PARTS:
        kind='capsule' if name.startswith(('upperarm','forearm','thigh','shin')) else 'ellipsoid'
        color=skin if name.startswith(('head','neck','nose','hand')) else suit
        if name.startswith(('hips','thigh','shin')):color=trousers
        if name.startswith(('shoe','eye','hair')):color='.035 .026 .022 1'
        if name=='shirt':color='.86 .87 .84 1'
        E.SubElement(body,'geom',name='customer_'+name,type=kind,size='.04 .08' if kind=='capsule' else '.06 .04 .08',
                     contype='0',conaffinity='0',density='0',group='2',rgba=color)


class CustomerActor:
    def __init__(self,model,data):
        self.model,self.data=model,data
        self.mocap=int(model.body_mocapid[model.body('demo_customer').id])
        self.ids={name:model.geom('customer_'+name).id for name in PARTS}
        # Compiled identity-frame optimization is invalid for animated local limbs.
        model.geom_sameframe[list(self.ids.values())]=0
        self.position=np.array([0.,-4.85]);self.heading=0.;self.distance=0.
        self.pose(self.position,0,False,hidden=True)

    def ellipsoid(self,name,pos,size,quat=None):
        i=self.ids[name];self.model.geom_pos[i]=pos;self.model.geom_size[i,:]=size
        self.model.geom_quat[i]=[1,0,0,0] if quat is None else quat
        self.model.geom_rbound[i]=max(size)

    def segment(self,name,a,b,radius):
        a,b=np.array(a),np.array(b);i=self.ids[name]
        self.model.geom_pos[i]=(a+b)/2;self.model.geom_size[i,:]=[radius,np.linalg.norm(b-a)/2,0]
        direction=(b-a)/max(np.linalg.norm(b-a),1e-12)
        q=np.array([1+direction[2],-direction[1],direction[0],0.])
        self.model.geom_quat[i]=q/np.linalg.norm(q) if np.linalg.norm(q)>1e-12 else [0,1,0,0]
        self.model.geom_rbound[i]=radius+np.linalg.norm(b-a)/2

    def pose(self,position,heading,moving,hidden=False):
        position=np.array(position,dtype=float)
        self.distance+=float(np.linalg.norm(position-self.position))
        self.position=position;self.heading=heading
        self.data.mocap_pos[self.mocap]=[*position,-10 if hidden else 0]
        yaw=heading-math.pi/2
        self.data.mocap_quat[self.mocap]=[math.cos(yaw/2),0,0,math.sin(yaw/2)]
        swing=.32*math.sin(self.distance*9) if moving else 0.
        self.ellipsoid('hips',(0,0,.91),(.175,.115,.14))
        self.ellipsoid('jacket',(0,0,1.23),(.235,.135,.29))
        self.ellipsoid('shirt',(0,.132,1.34),(.07,.012,.15))
        self.ellipsoid('neck',(0,0,1.51),(.048,.05,.075))
        self.ellipsoid('head',(0,0,1.65),(.095,.085,.125))
        self.ellipsoid('hair',(0,-.012,1.73),(.098,.08,.055))
        self.ellipsoid('nose',(0,.085,1.64),(.018,.022,.028))
        for side,x in (('l',-.035),('r',.035)):
            self.ellipsoid('eye_'+side,(x,.079,1.675),(.008,.008,.007))
        for side,x,phase in (('l',-.11,1),('r',.11,-1)):
            angle=swing*phase
            hip=np.array([x,0,.88]);knee=hip+[0,math.sin(angle)*.39,-math.cos(angle)*.39]
            ankle=knee+[0,math.sin(angle)*.35,-math.cos(angle)*.35]
            self.segment('thigh_'+side,hip,knee,.075)
            self.segment('shin_'+side,knee,ankle,.057)
            self.ellipsoid('shoe_'+side,ankle+[0,.055,-.075],(.075,.15,.055))
            shoulder=np.array([x*2.13,0,1.42]);elbow=shoulder+[0,-math.sin(angle)*.27,-.27]
            wrist=elbow+[0,-math.sin(angle)*.16,-.23]
            self.segment('upperarm_'+side,shoulder,elbow,.057)
            self.segment('forearm_'+side,elbow,wrist,.045)
            self.ellipsoid('hand_'+side,wrist+[0,0,-.045],(.038,.034,.07))
