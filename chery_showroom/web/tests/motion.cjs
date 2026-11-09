const esbuild=require('esbuild'),Module=require('node:module'),path=require('node:path'),assert=require('node:assert/strict');
const source=path.resolve(__dirname,'../src/motion.ts');
const code=esbuild.buildSync({entryPoints:[source],bundle:true,platform:'node',format:'cjs',write:false}).outputFiles[0].text;
const moduleUnderTest=new Module(source,module);moduleUnderTest._compile(code,source);
const {MotionBuffer,interpolate}=moduleUnderTest.exports;
function frame(revision,x=0,extra={}){return {run_id:'a',revision,sim_time:revision*.02,phase:'escort',robot_transforms:{pelvis:[x,0,1,1,0,0,0]},...extra};}
const x=s=>s?.robot_transforms.pelvis[0];
{
 const b=new MotionBuffer(100);b.push(frame(1,0),0);b.push(frame(2,10),200);
 assert.equal(x(b.sample(200)),5);assert.equal(x(b.sample(250)),7.5);assert.equal(x(b.sample(400)),10);
 assert.equal(b.sample(450),null,'no repeated redraw or extrapolation');
 assert.equal(b.push(frame(1,1000),500),false,'reject late packet');
 b.push(frame(3,20,{phase:'stopped'}),500);assert.equal(x(b.sample(500)),20,'Stop discards old movement');
 b.push(frame(0,0,{run_id:'b',sim_time:0}),600);assert.equal(x(b.sample(600)),0,'reset does not interpolate across runs');
}
{
 const b=new MotionBuffer();b.push(frame(1,1),0);b.push(frame(2,2),50);b.sample(1000);
 b.push(frame(3,100),1100);assert.equal(x(b.sample(1100)),100,'reconnection snaps to authoritative pose');
 assert.equal(b.push(frame(4,1,{sim_time:-1}),1200),false);
 assert.equal(b.push(frame(5,NaN),1300),false);
}
{
 const a=frame(1,0,{customer:{position:[0,0],heading:Math.PI-.1,hidden:false}});
 const b=frame(2,10,{customer:{position:[2,0],heading:-Math.PI+.1,hidden:false}});
 b.robot_transforms.pelvis[3]=-1;
 const s=interpolate(a,b,.5);assert.equal(x(s),5);assert(Math.abs(Math.abs(s.robot_transforms.pelvis[3])-1)<1e-10);
 assert(Math.abs(Math.abs(s.customer.heading)-Math.PI)<1e-10,'shortest yaw wrap');
 assert.equal(a.robot_transforms.pelvis[0],0,'no mutation of history');
}
{
 const b=new MotionBuffer();
 b.push(frame(1,0,{phase:'consultation',camera_view:'cinematic',camera_pose:{position:[0,0,0],quaternion:[1,0,0,0]}}),0);
 b.push(frame(2,0,{phase:'consultation',camera_view:'cinematic',camera_pose:{position:[10,0,0],quaternion:[1,0,0,0]}}),200);
 assert.equal(b.sample(200).camera_pose.position[0],5,'cinematic camera interpolates even while robot stands');
}
console.log('Motion tests passed: interpolation, quaternion signs, resets, Stop, stale packets, reconnection.');
