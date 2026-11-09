/** Runtime skinning of the original MakeHuman asset. Simulation owns root motion. */
import * as T from 'three';
export type CustomerFrame={run_id:string;sim_time:number;phase?:string;customer?:{position:number[];heading:number;hidden:boolean;moving?:boolean;paused?:boolean}};
const smooth=(a:number,b:number,x:number)=>T.MathUtils.smoothstep(x,a,b),V=(x:number,y:number,z:number)=>new T.Vector3(x,y,z);
export function createCustomerGait(placement:T.Group){
    const instance=placement.children[0].children[0] as T.Group;
    placement.updateWorldMatrix(true,true);
    const bounds=new T.Box3().setFromObject(instance),scale=new T.Vector3();instance.getWorldScale(scale);
    const metresPerUnit=scale.x,bones:T.Bone[]=[],rest:T.Vector3[]=[],names:Record<string,number>={};
    function bone(name:string,p:T.Vector3,parent?:string){
        const b=new T.Bone();b.name='customer_'+name;names[name]=bones.length;bones.push(b);rest.push(p.clone());b.position.copy(p);
        if(parent){b.position.sub(rest[names[parent]]);bones[names[parent]].add(b);}else instance.add(b);
    }
    bone('pelvis',V(.01,.83,.02));bone('chest',V(.01,1.09,.02),'pelvis');bone('head',V(.01,1.36,.06),'chest');
    for(const [s,sign] of [['left',1],['right',-1]] as const){
        bone(s+'_hip',V(.01+sign*.09,.79,.02),'pelvis');bone(s+'_knee',V(.01+sign*.13,.43,-.015),s+'_hip');bone(s+'_ankle',V(.01+sign*.155,.14,-.035),s+'_knee');
        bone(s+'_shoulder',V(.01+sign*.135,1.23,.035),'chest');bone(s+'_elbow',V(.01+sign*.18,1.02,.06),s+'_shoulder');bone(s+'_wrist',V(.01+sign*.15,.85,.13),s+'_elbow');
    }
    instance.updateWorldMatrix(true,true);const skeleton=new T.Skeleton(bones);skeleton.calculateInverses();
    const meshes:T.Mesh[]=[];instance.traverse(n=>{if(n instanceof T.Mesh)meshes.push(n);});
    const inverse=instance.matrixWorld.clone().invert(),skins:T.SkinnedMesh[]=[];let vertices=0,maxWeightError=0;
    for(const mesh of meshes){
        const geometry=mesh.geometry.clone().applyMatrix4(new T.Matrix4().multiplyMatrices(inverse,mesh.matrixWorld));
        const pos=geometry.getAttribute('position'),indices=new Uint16Array(pos.count*4),weights=new Float32Array(pos.count*4);
        const shoe=mesh.name.includes('shoes'),head=/eyebrow|eyelash|high-poly|ponytail|teeth/.test(mesh.name);
        for(let i=0;i<pos.count;i++){
            const x=pos.getX(i)-.01,y=pos.getY(i),w=new Map<number,number>();
            const add=(name:string,v:number)=>{if(v>0)w.set(names[name],(w.get(names[name])||0)+v);};const left=smooth(-.025,.025,x);
            if(head||y>1.3)add('head',1);
            else if(shoe){add('left_ankle',left);add('right_ankle',1-left);}
            else if(y<.84){
                const pelvis=smooth(.73,.84,y),knee=1-smooth(.37,.51,y),ankle=1-smooth(.19,.29,y);
                // Matching body/garment weights keep thighs inside the original skirt.
                const leg=1-pelvis;add('pelvis',1-leg);
                for(const [side,sw] of [['left',left],['right',1-left]] as const){add(side+'_hip',leg*sw*(1-knee));add(side+'_knee',leg*sw*knee*(1-ankle));add(side+'_ankle',leg*sw*knee*ankle);}
            }else{
                const arm=smooth(.105,.175,Math.abs(x))*(1-smooth(1.23,1.3,y)),forearm=1-smooth(.94,1.06,y),wrist=1-smooth(.82,.9,y),side=x>0?'left':'right';
                add(side+'_shoulder',arm*(1-forearm));add(side+'_elbow',arm*forearm*(1-wrist));add(side+'_wrist',arm*forearm*wrist);
                const chest=smooth(.86,1.02,y);add('chest',(1-arm)*chest);add('pelvis',(1-arm)*(1-chest));
            }
            const ranked=[...w].sort((a,b)=>b[1]-a[1]).slice(0,4),sum=ranked.reduce((n,p)=>n+p[1],0);
            ranked.forEach(([index,weight],slot)=>{indices[i*4+slot]=index;weights[i*4+slot]=weight/sum;});
            maxWeightError=Math.max(maxWeightError,Math.abs(1-weights.slice(i*4,i*4+4).reduce((a,b)=>a+b,0)));
        }
        geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(indices,4));geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));
        const skin=new T.SkinnedMesh(geometry,mesh.material);skin.name=mesh.name;skin.castShadow=mesh.castShadow;skin.receiveShadow=mesh.receiveShadow;skin.frustumCulled=false;
        instance.add(skin);skin.updateWorldMatrix(true,false);skin.bind(skeleton,skin.matrixWorld);mesh.removeFromParent();skins.push(skin);vertices+=pos.count;
    }
    instance.updateWorldMatrix(true,true);skeleton.update();
    const after=new T.Box3().setFromObject(instance),restBoundsError=Math.max(bounds.min.distanceTo(after.min),bounds.max.distanceTo(after.max));
    const neutral=bones.map(b=>({p:b.position.clone(),q:b.quaternion.clone()}));
    let run='',previous:T.Vector2|null=null,previousTime=0,phase=0,distance=0,speed=0,blend=0,targetBlend=0,paused=false,lastDraw=0,clampedTargets=0,stride=.72,pelvisDrop=0,samples=0,movingSamples=0,lastDelta=0,lastDt=0;
    const plants:Record<string,{p:T.Vector3;q:T.Quaternion}>={};
    function restore(){bones.forEach((b,i)=>{b.position.copy(neutral[i].p);b.quaternion.copy(neutral[i].q);});}
    function reset(){phase=0;distance=0;speed=0;blend=0;targetBlend=0;previous=null;previousTime=0;lastDraw=0;paused=false;clampedTargets=0;stride=.72;pelvisDrop=0;samples=0;movingSamples=0;lastDelta=0;lastDt=0;delete plants.left;delete plants.right;restore();}
    function leg(side:string,foot:T.Vector3,footQ=new T.Quaternion()){
        const hi=names[side+'_hip'],ki=names[side+'_knee'],ai=names[side+'_ankle'],hip=rest[hi].clone();hip.y-=pelvisDrop;
        const upper=rest[ki].clone().sub(rest[hi]),lower=rest[ai].clone().sub(rest[ki]),a=upper.length(),b=lower.length();
        const axis=foot.clone().sub(hip),raw=axis.length(),d=T.MathUtils.clamp(raw,Math.abs(a-b)+.001,a+b-.001);axis.normalize();if(Math.abs(raw-d)>.002)clampedTargets++;
        foot=hip.clone().addScaledVector(axis,d);const along=(a*a-b*b+d*d)/(2*d),height=Math.sqrt(Math.max(0,a*a-along*along));
        const forward=V(0,0,1).addScaledVector(axis,-axis.z).normalize(),knee=hip.clone().addScaledVector(axis,along).addScaledVector(forward,height);
        const qHip=new T.Quaternion().setFromUnitVectors(upper.clone().normalize(),knee.clone().sub(hip).normalize()),qLower=new T.Quaternion().setFromUnitVectors(lower.clone().normalize(),foot.clone().sub(knee).normalize());
        bones[hi].quaternion.copy(qHip);bones[ki].quaternion.copy(qHip).invert().multiply(qLower);bones[ai].quaternion.copy(qLower).invert().multiply(footQ);
    }
    function pose(){
        restore();if(blend<1e-5){delete plants.left;delete plants.right;pelvisDrop=0;instance.updateWorldMatrix(true,true);skeleton.update();return;}
        const targets:{side:string;foot:T.Vector3;q:T.Quaternion;stance:boolean}[]=[];
        pelvisDrop=0;
        for(const [side,offset] of [['left',0],['right',.5]] as const){
            const t=(phase+offset)%1,stance=.6,half=stride*stance/(2*metresPerUnit),swing=t>=stance?(t-stance)/(1-stance):0;
            const z=t<stance?half*(1-2*t/stance):half*(-1+2*(swing*swing*(3-2*swing))),lift=t<stance?0:Math.sin(Math.PI*swing)*.065;
            const foot=rest[names[side+'_ankle']].clone();
            // Centre each step under the hip, rather than behind the posed asset's hip.
            foot.z+=(.055+z)*blend;foot.y+=lift*blend;let q=new T.Quaternion();
            if(t<stance&&blend>.995){
                if(!plants[side])plants[side]={p:instance.localToWorld(foot.clone()),q:instance.getWorldQuaternion(new T.Quaternion())};
                foot.copy(instance.worldToLocal(plants[side].p.clone()));q=instance.getWorldQuaternion(new T.Quaternion()).invert().multiply(plants[side].q);
            }else delete plants[side];
            targets.push({side,foot,q,stance:t<stance});
            if(t<stance){
                const hip=rest[names[side+'_hip']],knee=rest[names[side+'_knee']],ankle=rest[names[side+'_ankle']];
                const length=hip.distanceTo(knee)+knee.distanceTo(ankle)-.002;
                const horizontal=(foot.x-hip.x)**2+(foot.z-hip.z)**2;
                // Only lower the pelvis as much as the planted leg needs; avoid a fixed crouch.
                const vertical=Math.sqrt(Math.max(0,length*length-horizontal));
                pelvisDrop=Math.max(pelvisDrop,hip.y-foot.y-vertical);
            }
        }
        pelvisDrop=T.MathUtils.clamp(pelvisDrop,0,.065);bones[names.pelvis].position.y-=pelvisDrop;
        for(const {side,foot,q} of targets){
            leg(side,foot,q);
            bones[names[side+'_shoulder']].rotation.x=(side==='left'?1:-1)*Math.sin(phase*2*Math.PI)*.14*blend;
            bones[names[side+'_elbow']].rotation.x=-.07*blend;
        }
        instance.updateWorldMatrix(true,true);skeleton.update();
    }
    function update(frame:CustomerFrame){
        const actor=frame.customer;if(frame.run_id!==run){reset();run=frame.run_id;}
        if(!actor||actor.hidden){reset();return;}
        const p=new T.Vector2(actor.position[0],actor.position[1]),dt=frame.sim_time-previousTime,travelled=previous?p.distanceTo(previous):0;paused=actor.paused===true;samples++;if(actor.moving)movingSamples++;lastDelta=travelled;lastDt=dt;
        if(previous&&dt>=0&&dt<.5&&travelled<.3&&!paused&&actor.moving){distance+=travelled;if(dt>1e-6){speed=travelled/dt;stride=T.MathUtils.damp(stride,.48+.32*T.MathUtils.clamp(speed/.8,0,1),6,dt);}phase=(phase+travelled/stride)%1;if(travelled>1e-7)targetBlend=1;}
        else if(!actor.moving&&!paused){targetBlend=0;speed=0;}
        if(!paused&&(dt>=.5||travelled>=.3)){targetBlend=0;blend=0;speed=0;}
        previous=p;previousTime=frame.sim_time;pose();
    }
    function animate(now:number){
        const dt=lastDraw?Math.min(.05,Math.max(0,(now-lastDraw)/1000)):0;lastDraw=now;if(paused)return false;
        const before=blend;blend=T.MathUtils.damp(blend,targetBlend,12,dt);if(Math.abs(blend-targetBlend)<.001)blend=targetBlend;if(before===blend)return false;pose();return true;
    }
    function evidence(){
        instance.updateWorldMatrix(true,true);
        return {samples,movingSamples,lastDelta,lastDt,run_id:run,sim_time:previousTime,rootPosition:placement.position.toArray(),feet_frame:'renderer_world',bones:bones.length,skinnedMeshes:skins.length,vertices,maxWeightError,restBoundsError,phase,distance,speed,stride,pelvisDrop,blend,paused,clampedTargets,
            planted:Object.fromEntries(Object.entries(plants).map(([s,p])=>[s,p.p.toArray()])),
            feet:Object.fromEntries(['left','right'].map(s=>[s,bones[names[s+'_ankle']].getWorldPosition(new T.Vector3()).toArray()])),
            jointRotations:Object.fromEntries(bones.map(b=>[b.name,b.quaternion.toArray()]))};
    }
    return {update,animate,reset,evidence};
}
