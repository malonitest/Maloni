// Exercise language selection and interruption without a microphone, TTS service or GPU.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const cues=JSON.parse(fs.readFileSync(path.join(root,'arrival_script.json'),'utf8')).cues;
const spoken=[],requests=[],elements=new Map();let cancelled=0,action;
const context=vm.createContext({
 token:'test',console,Map,Error,URL,
 document:{getElementById:id=>{if(!elements.has(id))elements.set(id,{textContent:''});return elements.get(id);}},
 window:{speechSynthesis:{cancel(){cancelled++;},getVoices:()=>[{lang:'cs-CZ'},{lang:'en-GB'}],speak:u=>spoken.push(u)},addEventListener(){}},
 SpeechSynthesisUtterance:function(text){this.text=text;},
 fetch:async url=>{requests.push(url);return {json:async()=>({language:'en',demo_audio_ready:true,demo_audio_language:'cs'})};},
 act:async value=>{action=value;}
});
vm.runInContext(fs.readFileSync(path.join(root,'arrival.js'),'utf8').replace('__ARRIVAL_CUES__',JSON.stringify(cues)),context);
(async()=>{
 await vm.runInContext('startArrival()',context);assert.equal(action,'scenario');
 const state={run_id:'one',demo_audio_ready:true,demo_audio_language:'cs',demo:{status:'welcome',remaining:49,elapsed:6,active:true,cue:cues[0].id}};
 const update=()=>{context.state=state;vm.runInContext('updateArrival(state)',context);};
 update();update();assert.equal(spoken.length,1,'Polling must not repeat the same speech');
 assert.equal(spoken[0].text,cues[0].en);assert.equal(spoken[0].lang,'en-US');assert.equal(spoken[0].voice.lang,'en-GB');
 assert.deepEqual(requests,['/state'],'Czech cache must never be fetched in English mode');
 assert(elements.get('demoStatus').textContent.includes('English browser voice'));
 const before=cancelled;state.demo.active=false;update();assert(cancelled>before,'Stop must cancel narration');
 context.fetch=async()=>({json:async()=>({demo_audio_ready:true})});action=null;
 await vm.runInContext('startArrival()',context);
 assert.equal(action,null,'Old backend must not start a mixed-language demo');
 assert(elements.get('error').textContent.includes('Restart the showroom'));
 console.log('PASS: English narration fallback, old Czech cache excluded, no repeated speech, Stop cancellation, legacy restart guard');
})().catch(e=>{console.error(e);process.exitCode=1;});
