import * as T from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

/** Concept geometry in metres, Z up, front +X. Only height is specified by the reference. */
export function createMaloni120() {
    const robot = new T.Group(); robot.name = 'maloni-humanoid-120';
    robot.userData = { model: 'MALONI Humanoid 120', height: 1.2, stage: 'concept', motionSource: 'independent differential-drive dynamics', reference: 'HELIOS revision 02', estimatedDimensions: true };
    const shell = new T.MeshPhysicalMaterial({color: '#eeeae2', roughness: .32, clearcoat: .4});
    const dark = new T.MeshStandardMaterial({color: '#202933', roughness: .55});
    const glass = new T.MeshPhysicalMaterial({color: '#06141e', roughness: .15, clearcoat: 1});
    const blue = new T.MeshStandardMaterial({color: '#008eff', emissive: '#006bd6', emissiveIntensity: .5});
    function box(parent:T.Object3D,name:string,size:number[],pos:number[],mat:T.Material,r=.025) {
        const mesh=new T.Mesh(new RoundedBoxGeometry(size[0],size[1],size[2],3,r),mat);
        mesh.name=name;mesh.position.set(pos[0],pos[1],pos[2]);mesh.castShadow=true;parent.add(mesh);return mesh;
    }
    function sphere(parent:T.Object3D,name:string,pos:number[],scale:number[],mat:T.Material) {
        const mesh=new T.Mesh(new T.SphereGeometry(1,24,16),mat);mesh.name=name;
        mesh.position.set(pos[0],pos[1],pos[2]);mesh.scale.set(scale[0],scale[1],scale[2]);parent.add(mesh);return mesh;
    }
    box(robot,'base-bumper',[.40,.53,.12],[0,0,.12],dark);
    const skirt=new T.Mesh(new T.CylinderGeometry(.17,.27,.51,48),shell);
    skirt.name='lower-shell';skirt.rotation.x=Math.PI/2;skirt.scale.z=.82;skirt.position.z=.40;robot.add(skirt);
    const wheels:T.Mesh[]=[];
    for(const side of [-1,1]) {
        const wheel=new T.Mesh(new T.CylinderGeometry(.135,.135,.055,32),dark);
        wheel.name=side<0?'right-drive-wheel':'left-drive-wheel';wheel.position.set(0,side*.25,.14);robot.add(wheel);wheels.push(wheel);
        const rim=new T.Mesh(new T.TorusGeometry(.108,.004,8,32),blue);
        rim.rotation.x=Math.PI/2;rim.position.set(0,side*.28,.14);robot.add(rim);
        sphere(robot,'support-caster',[-.13,side*.17,.035],[.03,.025,.035],dark);
    }
    box(robot,'lidar',[.055,.105,.035],[.226,0,.19],glass,.01);
    box(robot,'blue-base-trim',[.018,.43,.008],[.205,0,.14],blue,.003);
    const torso=new T.Group();torso.name='torso_link';robot.add(torso);
    box(torso,'chest-shell',[.25,.32,.33],[0,0,.79],shell,.065);
    box(torso,'neck',[.09,.10,.06],[0,0,.98],dark,.012);
    const head=new T.Group();head.name='head_link_visual';head.position.z=1.085;robot.add(head);
    box(head,'head-shell',[.23,.29,.23],[0,0,0],shell,.07);
    box(head,'face-display',[.018,.235,.14],[.118,0,0],glass,.035);
    for(const side of [-1,1]) {
        sphere(head,'display-eye',[.130,side*.06,.005],[.004,.018,.028],blue);
        sphere(head,'camera',[.117,side*.065,.086],[.008,.009,.009],glass);
        const shoulder=new T.Group();shoulder.name=`shoulder-${side}`;shoulder.position.set(0,side*.205,.89);torso.add(shoulder);
        sphere(shoulder,'shoulder-joint',[0,0,0],[.072,.066,.07],dark);
        box(shoulder,'upper-arm',[.10,.10,.18],[.015,side*.02,-.12],shell,.035);
        sphere(shoulder,'elbow',[.018,side*.02,-.23],[.05,.05,.05],dark);
        const elbow=new T.Group();elbow.name=`elbow-${side}`;elbow.position.set(.018,side*.02,-.23);shoulder.add(elbow);
        box(elbow,'forearm',[.09,.09,.17],[.027,0,-.10],shell,.03);
        sphere(elbow,'fixed-palm',[.047,0,-.215],[.045,.043,.065],shell);
        box(torso,'chest-accent',[.012,.009,.19],[.127,side*.12,.79],blue,.003);
    }
    for(let row=0;row<3;row++)for(let col=0;col<7;col++)sphere(torso,'speaker-hole',[.129,(col-3)*.012,.88+row*.012],[.002,.0025,.0025],dark);
    const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;
    const ctx=canvas.getContext('2d')!;ctx.fillStyle='#eeeae2';ctx.fillRect(0,0,512,128);ctx.fillStyle='#142d4c';ctx.font='bold 64px sans-serif';ctx.textAlign='center';ctx.fillText('MALONI',256,86);
    const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
    const label=new T.Mesh(new T.PlaneGeometry(.15,.0375),new T.MeshBasicMaterial({map:texture}));label.rotation.set(Math.PI/2,Math.PI/2,0);label.position.set(.131,0,.80);torso.add(label);
    sphere(robot,'emergency-stop',[-.10,-.12,.96],[.018,.018,.018],new T.MeshStandardMaterial({color:'#db2020'}));
    let previous:T.Vector2|null=null,previousTime:number|null=null;
    function update(x:number,y:number,yaw:number,time?:number,joints?:Record<string,number>,wheelAngles?:number[]) {
        const current=new T.Vector2(x,y);
        if(previous&&previousTime!==null&&time!==undefined&&time>=previousTime&&time-previousTime<1) {
            const distance=current.clone().sub(previous).dot(new T.Vector2(Math.cos(yaw),Math.sin(yaw)));
            if(Math.abs(distance)<.5)for(const wheel of wheels)wheel.rotateY(distance/.135);
        } else for(const wheel of wheels)wheel.rotation.set(0,0,0);
        if(wheelAngles?.length===2)wheels.forEach((wheel,i)=>wheel.rotation.y=wheelAngles[i]);
        head.rotation.z=joints?.head_yaw||0;head.rotation.y=joints?.head_pitch||0;
        for(const [side,prefix] of [[1,'left'],[-1,'right']] as const) {
            const shoulder=robot.getObjectByName(`shoulder-${side}`)!;
            shoulder.rotation.y=joints?.[`${prefix}_shoulder_pitch`]||0;
            shoulder.rotation.x=joints?.[`${prefix}_shoulder_roll`]||0;
            robot.getObjectByName(`elbow-${side}`)!.rotation.y=-(joints?.[`${prefix}_elbow`]||0);
        }
        previous=current;previousTime=time??null;robot.position.set(x,y,0);robot.rotation.z=yaw;
    }
    return {robot,update,evidence:robot.userData};
}
