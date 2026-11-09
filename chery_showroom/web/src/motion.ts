import {Quaternion} from 'three';
export type SimulationState = {
    run_id: string; revision: number; sim_time: number; phase?: string; gesture?: boolean;
    backend?: string; selected?: string; camera_view?: string;
    robot_model?: string; robot_joints?: Record<string,number>; wheel_angles?: number[];
    robot_transforms?: Record<string,number[]>;
    customer?: {position: number[]; heading: number; hidden: boolean; moving?: boolean; paused?:boolean};
    camera_pose?: {position: number[]; quaternion: number[]};
};
type Frame={state: SimulationState;received: number};
const angle=(a:number,b:number,t:number)=>a+Math.atan2(Math.sin(b-a),Math.cos(b-a))*t;
function quaternion(a:number[],b:number[],t:number):number[]{
    const q=new Quaternion(a[1],a[2],a[3],a[0]).normalize();
    q.slerp(new Quaternion(b[1],b[2],b[3],b[0]).normalize(),t);
    return [q.w,q.x,q.y,q.z];
}
function vector(a:number[],b:number[],t:number){return a.map((v,i)=>v+(b[i]-v)*t);}
export function interpolate(a:SimulationState,b:SimulationState,t:number):SimulationState{
    const robot:Record<string,number[]>={};
    for(const [name,pose] of Object.entries(b.robot_transforms||{})){
        const old=a.robot_transforms?.[name];
        robot[name]=old?[...vector(old.slice(0,3),pose.slice(0,3),t),...quaternion(old.slice(3),pose.slice(3),t)]:[...pose];
    }
    let customer=b.customer;
    if(a.customer&&b.customer&&!a.customer.hidden&&!b.customer.hidden)customer={...b.customer,position:vector(a.customer.position,b.customer.position,t),heading:angle(a.customer.heading,b.customer.heading,t)};
    let camera_pose=b.camera_pose;
    if(a.camera_pose&&b.camera_pose)camera_pose={position:vector(a.camera_pose.position,b.camera_pose.position,t),quaternion:quaternion(a.camera_pose.quaternion,b.camera_pose.quaternion,t)};
    const robot_joints=Object.fromEntries(Object.entries(b.robot_joints||{}).map(([k,v])=>[k,(a.robot_joints?.[k]??v)+(v-(a.robot_joints?.[k]??v))*t]));
    const wheel_angles=b.wheel_angles?.map((v,i)=>(a.wheel_angles?.[i]??v)+(v-(a.wheel_angles?.[i]??v))*t);
    return {...b,robot_joints,wheel_angles,sim_time:a.sim_time+(b.sim_time-a.sim_time)*t,robot_transforms:robot,customer,camera_pose};
}
function moving(state:SimulationState){return ['escort','aligning','manual','presentation','greeting_gesture'].includes(state.phase||'')||!!state.gesture||!!state.customer?.moving||state.camera_view==='cinematic';}
export class MotionBuffer{
    private frames:Frame[]=[];
    private key='';
    constructor(readonly delayMs=100,readonly staleMs=500){}
    push(state:SimulationState,received:number):boolean{
        if(!state||typeof state.run_id!=='string'||(!Number.isInteger(state.revision)||state.revision<0)||!Number.isFinite(state.sim_time)||!Number.isFinite(received))return false;
        for(const pose of Object.values(state.robot_transforms||{}))if(pose.length!==7||!pose.every(Number.isFinite)||Math.hypot(...pose.slice(3))<1e-12)return false;
        const previous=this.frames.at(-1);
        if(previous&&previous.state.run_id===state.run_id&&(state.revision<=previous.state.revision||state.sim_time<previous.state.sim_time))return false;
        if(!previous||previous.state.run_id!==state.run_id||received-previous.received>this.staleMs||!moving(state)){
            this.frames=[];this.key='';
        }
        // Copy packets: the caller can continue handling metadata without mutating history.
        this.frames.push({state:structuredClone(state),received});
        if(this.frames.length>32)this.frames.shift();
        return true;
    }
    sample(now:number):SimulationState|null{
        if(!this.frames.length)return null;
        const last=this.frames.at(-1)!;let a=last,b=last,t=1;
        const target=now-this.delayMs;
        if(moving(last.state)&&now-last.received<=this.staleMs){
            a=this.frames[0];b=a;
            for(let i=1;i<this.frames.length;i++){
                b=this.frames[i];if(b.received>=target)break;a=b;
            }
            if(a!==b)t=Math.max(0,Math.min(1,(target-a.received)/(b.received-a.received)));
        }
        const key=`${last.state.run_id}/${a.state.revision}/${b.state.revision}/${t}`;
        if(key===this.key)return null;this.key=key;
        return a===b?structuredClone(b.state):interpolate(a.state,b.state,t);
    }
    clear(){this.frames=[];this.key='';}
}
