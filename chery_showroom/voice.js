// Same WebRTC protocol used by the existing Buddha conversation panel.
let cloudPC=null,cloudDC=null,cloudMic=null,cloudSession=null,cloudAttempt=0,cloudRun=null,cloudActive=false,cloudContext='',cloudTranscript='',cloudTimer=null;
async function voiceRequest(path,value){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Showroom-Token':token},body:JSON.stringify(value)});const data=await r.json();if(!r.ok)throw Error(data.error||'The voice service failed.');return data}
function cloudEvent(type,content){if(cloudDC?.readyState==='open')cloudDC.send(JSON.stringify({type,content,event_id:crypto.randomUUID(),delegation_id:null}))}
async function stopCloud(interruption=false){++cloudAttempt;cloudActive=false;clearTimeout(cloudTimer);cloudTranscript='';cloudDC?.close();cloudPC?.close();cloudMic?.getTracks().forEach(t=>t.stop());cloudDC=null;cloudPC=null;cloudMic=null;document.getElementById('cloudAudio').srcObject=null;const sid=cloudSession;cloudSession=null;if(sid)void voiceRequest('/cancel',{session_id:sid,interruption,run_id:cloudRun}).catch(()=>{});document.getElementById('cloudStatus').textContent='Cloud conversation ended.'}
function voiceCommand(text){
  if(cloudRun&&cloudRun!==previousRun)return;
  // Speech and text share the local visit/controller; the cloud never decides motion.
  return act('chat',text);
}
function flushCloudTranscript(){
  const text=cloudTranscript.trim();cloudTranscript='';
  if(text){log.textContent+='\nYou: '+text;void voiceCommand(text)}
}
async function startCloud(){browserVoice.cancel();await stopCloud(true);let mine=++cloudAttempt;document.getElementById('cloudStatus').textContent='Connecting English voice…';try{const sr=await fetch('/state',{headers:{'X-Showroom-Token':token}});const state=await sr.json();cloudRun=state.run_id;if(state.language!=='en')throw Error(L('Cloud voice is available in English. Use browser voice for Czech.'));if(!state.voice_configured)throw Error('Set OPENAI_API_KEY in the environment and restart the showroom.');let mic=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});if(mine!==cloudAttempt){mic.getTracks().forEach(t=>t.stop());return}cloudMic=mic;const pc=new RTCPeerConnection();cloudPC=pc;mic.getTracks().forEach(t=>pc.addTrack(t,mic));const dc=pc.createDataChannel('oai-events');cloudDC=dc;dc.onmessage=({data})=>{if(mine!==cloudAttempt)return;let e;try{e=JSON.parse(data)}catch{return}if(e.type==='session.started'){cloudActive=true;cloudContext='';document.getElementById('cloudStatus').textContent='Listening in English.'}if(e.type==='session.input_transcript.delta'){cloudTranscript+=e.delta;clearTimeout(cloudTimer);cloudTimer=setTimeout(flushCloudTranscript,850)}if(e.type==='session.output_transcript.delta'){log.textContent+=e.delta;log.scrollTop=log.scrollHeight}if(e.type==='error'||e.type==='session.closed'){void act('stop');void stopCloud()}};pc.ontrack=({streams,track})=>{if(mine!==cloudAttempt)return;let audio=document.getElementById('cloudAudio');audio.srcObject=streams[0]||new MediaStream([track]);audio.play().catch(()=>{})};pc.onconnectionstatechange=()=>{if(['failed','disconnected'].includes(pc.connectionState)){void act('stop');void stopCloud()}};await pc.setLocalDescription(await pc.createOffer());await new Promise((resolve,reject)=>{if(pc.iceGatheringState==='complete')return resolve();let timer=setTimeout(()=>reject(Error('The audio connection was not ready.')),8000);pc.addEventListener('icegatheringstatechange',()=>{if(pc.iceGatheringState==='complete'){clearTimeout(timer);resolve()}})});let result=await voiceRequest('/session',{sdp:pc.localDescription.sdp,run_id:cloudRun});if(mine!==cloudAttempt){void voiceRequest('/cancel',{session_id:result.session_id,interruption:true}).catch(()=>{});return}cloudSession=result.session_id;await pc.setRemoteDescription({type:'answer',sdp:result.sdp});setTimeout(()=>{if(mine===cloudAttempt&&!cloudActive)void stopCloud()},15000)}catch(e){if(mine===cloudAttempt){if(latestState?.interactive?.active)void act('stop');await stopCloud();document.getElementById('cloudStatus').textContent=e.message}}}
function cloudUpdate(s){
  if(cloudRun&&cloudRun!==s.run_id){void stopCloud();cloudRun=null;return}
  const context=JSON.stringify({run_id:s.run_id,selected:s.selected,phase:s.phase,
    error:s.error,conversation:s.conversation,message_id:s.message_id,message:s.message});
  if(cloudActive&&context!==cloudContext){
    const previous=cloudContext ? JSON.parse(cloudContext) : null;cloudContext=context;
    cloudEvent('session.thinking.append','Actual local controller state: '+context);
    if(!previous||previous.message_id!==s.message_id||previous.message!==s.message)
      cloudEvent('session.commentary.append','LOCAL_REPLY: '+JSON.stringify(s.message)+'. Speak only this message in English.');
  }
}
function cloudText(text){return voiceCommand(text)}
window.addEventListener('pagehide',()=>{cloudMic?.getTracks().forEach(t=>t.stop());cloudPC?.close()});
