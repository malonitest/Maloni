const arrivalCues=__ARRIVAL_CUES__;
// English cached clips, with local browser speech when no English cache is prepared.
let demoClips=new Map(),demoPlaying=null,demoRun=null,demoReady=false,demoLoading=0,demoSpeechKey=null;
function stopDemoAudio(){
  if(demoPlaying){demoPlaying.pause();demoPlaying.currentTime=0;demoPlaying=null}
  if(demoSpeechKey){window.speechSynthesis?.cancel();demoSpeechKey=null}
}
async function startArrival(){
  const attempt=++demoLoading;stopDemoAudio();window.speechSynthesis?.cancel();
  try{
    const state=await (await fetch('/state',{headers:{'X-Showroom-Token':token}})).json();
    if(state.language!=='en')throw Error('Restart the showroom and refresh with Ctrl+F5 to enable the English visit.');
    if(typeof stopCloud==='function')await stopCloud();
    if(state.demo_audio_ready&&state.demo_audio_language==='en')for(const cue of arrivalCues){
      if(!demoClips.has(cue.id)){
        const response=await fetch('/demo-audio/'+cue.id+'.wav',{headers:{'X-Showroom-Token':token}});
        if(!response.ok)throw Error('The English recording is unavailable.');
        const audio=new Audio(URL.createObjectURL(await response.blob()));audio.preload='auto';
        audio.muted=true;await audio.play();audio.pause();audio.currentTime=0;audio.muted=false;
        demoClips.set(cue.id,audio);
      }
    }
    if(attempt!==demoLoading)return;
    demoReady=true;await act('scenario');
  }catch(e){document.getElementById('error').textContent=e.message}
}
function updateArrival(s){
  const demo=s.demo;if(!demo)return;
  const labels={idle:'Ready',arrival:'Customer arriving',welcome:'Welcome',escort:'Escort to CHERY',
    presentation:'Vehicle presentation',completed:'Demo completed',stopped:'Demo stopped',failed:'Demo interrupted'};
  const voice=s.demo_audio_ready&&s.demo_audio_language==='en'?'AI-generated English voices':
    window.speechSynthesis?'English browser voice':'English subtitles';
  document.getElementById('demoStatus').textContent=(labels[demo.status]||demo.status)+' · '+demo.remaining.toFixed(1)+' s remaining · '+voice;
  const cue=arrivalCues.find(c=>c.id===demo.cue);
  document.getElementById('demoSubtitle').textContent=cue?cue.en:'';
  if(demoRun!==s.run_id){stopDemoAudio();demoRun=s.run_id}
  if(!demo.active||!cue){stopDemoAudio();return}
  if(!demoReady)return;
  if(demoClips.has(cue.id)&&s.demo_audio_language==='en'){
    const audio=demoClips.get(cue.id),offset=demo.elapsed-cue.start;
    if(demoPlaying!==audio){
      stopDemoAudio();demoPlaying=audio;audio.currentTime=Math.min(offset,audio.duration||offset);
      if(offset<(audio.duration||Infinity))audio.play().catch(()=>{
        document.getElementById('error').textContent='Audio was blocked. Click Start customer arrival to enable playback.';
      });
    }else if(!audio.ended&&Math.abs(audio.currentTime-offset)>.3)audio.currentTime=Math.min(offset,audio.duration||offset);
  }else if(window.speechSynthesis&&demoSpeechKey!==s.run_id+':'+cue.id){
    stopDemoAudio();demoSpeechKey=s.run_id+':'+cue.id;
    const utterance=new SpeechSynthesisUtterance(cue.en);utterance.lang='en-US';utterance.rate=1.2;
    const voice=window.speechSynthesis.getVoices().find(v=>/^en(?:-|$)/i.test(v.lang));if(voice)utterance.voice=voice;
    utterance.onerror=e=>{if(!['canceled','interrupted'].includes(e.error))document.getElementById('error').textContent='English speech is unavailable. Follow the English subtitles.'};
    window.speechSynthesis.speak(utterance);
  }
}
window.addEventListener('pagehide',()=>{++demoLoading;stopDemoAudio();for(const audio of demoClips.values())URL.revokeObjectURL(audio.src)});
