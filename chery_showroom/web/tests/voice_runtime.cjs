// Actual local controller/HTTP with mocked speech devices; no renderer or cloud call.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  assert(process.env.SHOWROOM_URL,'Set the local showroom URL');
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,
    args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    const page=await browser.newPage();const errors=[],actions=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(new URL(request.url()).pathname==='/action')actions.push(JSON.parse(request.postData()));});
    // Rendering is covered by native.cjs; this test isolates the audio/controller path.
    await page.route('**/web/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Audio transport test</title>'}));
    await page.addInitScript(()=>{
      window.__spoken=[];
      speechSynthesis.speak=utterance=>window.__spoken.push(utterance.text);
      window.SpeechRecognition=class {
        constructor(){window.__recognition=this;}start(){}
        abort(){this.onerror?.({error:'aborted'});}
      };
    });
    await page.goto(process.env.SHOWROOM_URL);
    await page.waitForFunction(()=>latestState?.run_id);
    await page.locator('#language').selectOption('cs');
    await page.waitForFunction(()=>latestState?.language==='cs'&&document.getElementById('showVoice').textContent==='Mluvit');
    await page.locator('#language').selectOption('en');
    await page.waitForFunction(()=>latestState?.language==='en'&&document.getElementById('showVoice').textContent==='Speak');
    assert(await page.locator('#showVoice').isVisible(),'Voice entry is visible above the gallery');await page.locator('#showVoice').click();assert(await page.locator('#voice').isChecked());
    await page.evaluate(()=>window.__recognition.onresult({results:[[{transcript:'How many seats does CHERY Tiggo 8 Pro have?'}]]}));
    await page.waitForFunction(()=>window.__spoken.some(text=>text.includes('Malaysian reference version has seven seats')));
    assert(actions.some(value=>value.action==='chat'&&value.text.includes('seats')),'Transcript reaches the actual local controller');
    await page.locator('#mic').click();
    const before=await page.evaluate(()=>{window.__oldRecognition=window.__recognition;return latestState.run_id;});
    await page.getByRole('button',{name:'Reset',exact:true}).click();
    await page.waitForFunction(run=>latestState?.run_id!==run,before);
    const count=actions.length;
    await page.evaluate(()=>window.__oldRecognition.onresult({results:[[{transcript:'Escort me to BMW X1'}]]}));
    await page.waitForTimeout(150);
    assert.equal(actions.length,count,'Reset rejects the previous microphone session');
    await page.locator('#mic').click();
    await page.evaluate(()=>window.__recognition.onerror({error:'not-allowed'}));
    await page.locator('#error').filter({hasText:'microphone'}).waitFor();
    await page.locator('#text').fill('What is the length of Volvo XC60?');
    await page.locator('form button').click();
    await page.waitForFunction(()=>window.__spoken.some(text=>text.includes('4708')));
    assert.deepEqual(errors,[]);
    const result={passed:true,actualLocalController:true,finalTranscript:true,spokenCatalogReply:true,
      resetRejectsOldTranscript:true,deniedMicrophoneTextFallback:true,visibleVoiceButton:true,switchesVoiceLabel:true,physicalAudioTested:false,cloudCalls:0};
    if(process.env.REVIEW_OUTPUT)fs.writeFileSync(process.env.REVIEW_OUTPUT,JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
