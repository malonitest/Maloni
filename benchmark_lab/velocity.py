"""Ground-truth velocity feedback for the existing policy (simulation only)."""
import hashlib
import json
from pathlib import Path
import numpy as np

CALIBRATION = Path(__file__).with_name('velocity_config.json')
KEY_COMMANDS = {ord('W'):(.5,0,0),ord('S'):(-.3,0,0),ord('A'):(0,.2,0),
    ord('D'):(0,-.2,0),ord('Q'):(0,0,.2),ord('E'):(0,0,-.2),32:(0,0,0),
    265:(.5,0,0),264:(-.3,0,0),263:(0,0,.2),262:(0,0,-.2)}

class VelocityController:
    def __init__(self, path=CALIBRATION):
        payload=Path(path).read_bytes()
        self.digest=hashlib.sha256(payload).hexdigest()
        self.cfg=json.loads(payload)
        self.reset()

    def reset(self):
        self.integral=np.zeros(3)
        self.filtered=np.zeros(3)
        self.previous=np.zeros(3)
        self.target=np.zeros(3)

    def update(self, target, measured, dt):
        target=np.asarray(target,dtype=float); measured=np.asarray(measured,dtype=float)
        if target.shape!=(3,) or measured.shape!=(3,) or not np.isfinite([target,measured]).all() or not np.isfinite(dt) or dt<=0:
            raise ValueError('Expected finite three-axis velocities and positive dt')
        self.filtered += dt/(self.cfg['filter_s']+dt)*(measured-self.filtered)
        changed=(np.sign(target)!=np.sign(self.target)) | (target==0)
        self.integral[changed]=0
        error=target-self.filtered
        feed=np.zeros(3)
        for axis,table in enumerate(self.cfg['axes']):
            if target[axis]!=0:
                branch=table['positive' if target[axis]>0 else 'negative']
                feed[axis]=np.sign(target[axis])*np.interp(abs(target[axis]),branch['speed'],branch['input'])
        kp=np.asarray(self.cfg['kp']); ki=np.asarray(self.cfg['ki'])
        low=np.asarray(self.cfg['lower']); high=np.asarray(self.cfg['upper'])
        candidate=np.clip(self.integral+ki*error*dt,-np.asarray(self.cfg['integral_limit']),self.cfg['integral_limit'])
        unconstrained=feed+kp*error+candidate
        limited=np.clip(unconstrained,low,high)
        delta=np.asarray(self.cfg['slew_per_s'])*dt
        output=np.clip(limited,self.previous-delta,self.previous+delta)
        # Conditional integration includes rate limiting as well as saturation.
        integrate=(np.abs(output-unconstrained)<1e-12) | (error*(unconstrained-output)<0)
        self.integral=np.where(integrate,candidate,self.integral)
        self.integral[target==0]=0
        output[target==0]=0  # stop must not retain dead-zone compensation
        self.previous=output.copy(); self.target=target.copy()
        return output
