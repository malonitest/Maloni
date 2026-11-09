const assert=require('node:assert/strict');
const {BrowserVoice}=require('../../browser_voice.js');
const transcripts=[],errors=[],listening=[],spoken=[];
let latest,aborts=0,cancels=0;
class Recognition {constructor(){latest=this;}start(){}abort(){aborts++;this.onerror?.({error:'aborted'});}}
const environment={SpeechRecognition:Recognition,SpeechSynthesisUtterance:class {constructor(text){this.text=text;}},
  speechSynthesis:{cancel(){cancels++;},speak(value){spoken.push(value);}}};
const voice=new BrowserVoice({environment,onTranscript:text=>transcripts.push(text),onError:e=>errors.push(e),onListening:x=>listening.push(x)});
function result(recognition,text){recognition.onresult({results:[Object.assign([{transcript:text}],{isFinal:true})]});}
assert(voice.listen());const old=latest;
voice.cancel();result(old,'escort me');assert.deepEqual(transcripts,[],'Stop/reset rejects late transcription');
voice.listen();const once=latest;result(once,'  Hello  ');result(once,'Hello');
assert.deepEqual(transcripts,['Hello'],'Only one final transcript per recognition');
let current=true;voice.listen(()=>current);current=false;result(latest,'old run');assert.equal(transcripts.length,1);
voice.listen();latest.onerror({error:'not-allowed'});assert.equal(errors.length,1);assert.equal(listening.at(-1),false);
voice.listen();const pending=latest;assert(voice.speak('Local reply'));result(pending,'echo');assert.equal(transcripts.length,1);
assert.equal(spoken.at(-1).text,'Local reply');assert.equal(spoken.at(-1).lang,'en-US');
voice.listen(()=>true,'cs');assert.equal(latest.lang,'cs-CZ');
voice.speak('Česká odpověď. Zdroj: https://example.com/long-address','cs');
assert.equal(spoken.at(-1).lang,'cs-CZ');assert(!spoken.at(-1).text.includes('https://'));
const failedSpeech=spoken.at(-1),errorCount=errors.length;failedSpeech.onerror();
assert.equal(errors.length,errorCount+1);voice.cancel();failedSpeech.onerror();assert.equal(errors.length,errorCount+1);
assert(aborts>=4&&cancels>=4);
const noService=new BrowserVoice({environment:{},onTranscript:()=>{},onError:e=>errors.push(e)});
assert.equal(noService.listen(),false);assert.equal(noService.speak('text remains'),false);
const broken=new BrowserVoice({environment:{SpeechRecognition:class {start(){throw Error('denied');}abort(){}}},onTranscript:()=>{},onError:e=>errors.push(e)});
assert.equal(broken.listen(),false);
console.log('Browser voice passed: Stop/reset, stale results, duplicate finals, denied microphone, echo prevention, unavailable services.');
