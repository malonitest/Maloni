// Manual commands are leases, independent of the normal dashboard heartbeat.
let manualSequence=0,manualTimer=null,manualHeld=null,renderMetric=null;
const operatorPanel=document.getElementById('operatorPanel');
const visitorBar=document.getElementById('visitorBar');visitorBar.closest('section').before(visitorBar);visitorBar.appendChild(document.getElementById('car'));
window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===document.getElementById('showroom3d').contentWindow&&event.data?.type==='showroom-render-metrics'&&Number.isFinite(event.data.render_ms))renderMetric={ms:event.data.render_ms,time:performance.now()};});
async function manualPacket(v,begin=false){
  if(!latestState)return;
  const body={action:'manual_control',run_id:latestState.run_id,sequence:++manualSequence,begin,vx:v[0],vy:v[1],yaw_rate:v[2]};
  try{const response=await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json','X-Showroom-Token':token},body:JSON.stringify(body)});
    if(!response.ok){manualRelease(false);document.getElementById('operatorStatus').textContent=L('Manual control unavailable. End the visit and clear faults.');}
  }catch{manualRelease(false);}
}
function manualRelease(send=true){clearInterval(manualTimer);manualTimer=null;const was=manualHeld;manualHeld=null;if(send&&was)void manualPacket([0,0,0]);}
function manualStart(v){if(!operatorPanel.open||latestState?.interactive?.active||latestState?.error||latestState?.demo?.active)return;
  manualRelease();manualHeld=v;void manualPacket(v,true);manualTimer=setInterval(()=>{if(manualHeld)void manualPacket(manualHeld)},80);
}
operatorPanel.querySelectorAll('[data-drive]').forEach(button=>{
  button.addEventListener('pointerdown',event=>{event.preventDefault();button.setPointerCapture(event.pointerId);manualStart(JSON.parse(button.dataset.drive));});
  for(const name of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(name,()=>manualRelease());
});
const manualKeys={w:[.5,0,0],s:[-.3,0,0],a:[0,.2,0],d:[0,-.2,0],q:[0,0,.2],e:[0,0,-.2]};
window.addEventListener('keydown',event=>{if(event.target.closest('input,textarea,select')||!operatorPanel.open)return;
  if(event.code==='Space'){event.preventDefault();manualRelease();void act('stop');return;}
  if(manualKeys[event.key.toLowerCase()]&&!event.repeat){event.preventDefault();manualStart(manualKeys[event.key.toLowerCase()]);}
});
window.addEventListener('keyup',event=>{if(manualKeys[event.key.toLowerCase()])manualRelease();});
window.addEventListener('blur',()=>manualRelease());
document.addEventListener('visibilitychange',()=>{if(document.hidden)manualRelease();});
operatorPanel.addEventListener('toggle',()=>{if(!operatorPanel.open)manualRelease();});
function visitorPrimary(){const stage=latestState?.interactive?.stage;
  if(!latestState?.interactive?.active)return act('start_visit');
  if(stage==='choose'){document.getElementById('car').focus();return act('select');}
  if(stage==='offer')return send('yes');
  if(['paused','presentation'].includes(stage))return act('interactive_continue');
  if(stage==='questions')return act('end_visit');
}
function updateOperator(s){
  document.getElementById('topVoiceError').textContent=browserVoiceError?' · '+browserVoiceError:'';
  manualSequence=Math.max(manualSequence,s.manual_control?.sequence??0);
  const locked=!!(s.interactive?.active||s.demo?.active||s.error);
  operatorPanel.querySelectorAll('[data-drive]').forEach(button=>button.disabled=locked);
  if(locked&&manualHeld)manualRelease();
  document.getElementById('operatorStatus').textContent=locked?L('Manual control unavailable. End the visit and clear faults.'):(s.manual_control?.requires_new_press?L('Manual control expired. Release and press again.'):L('Hold a button or W/S/A/D/Q/E. Release to stop.'));
  document.getElementById('operatorDiagnostics').textContent=JSON.stringify({...s.diagnostics,render_cpu_ms:renderMetric&&performance.now()-renderMetric.time<3000?renderMetric.ms:L('Unavailable')},null,2);
  const stage=s.interactive?.stage??'idle';
  document.getElementById('visitStep').textContent=L('Visit stage')+': '+L(stage)+(s.error?' · '+s.error:'');
  const labels={choose:'Select car',offer:'Accept accompaniment',paused:'Continue',presentation:'Continue',questions:'End visit'};
  const primary=document.getElementById('visitPrimary');primary.textContent=L(s.interactive?.active?(labels[stage]||'Please wait'):'Start visit');
  primary.disabled=s.interactive?.active?!labels[stage]:!s.ready_for_visit;
  document.getElementById('topContinue').disabled=!s.interactive?.active||!['paused','presentation'].includes(stage);
}
