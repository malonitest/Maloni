const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const out=process.env.REVIEW_OUTPUT;fs.mkdirSync(out,{recursive:true});
 const result={passed:false,scenarios:[],errors:[]};
 const progress=step=>{result.step=step;fs.writeFileSync(path.join(out,'bilingual-result.json'),JSON.stringify(result,null,2));console.log(step);};
 let page;try {
  progress('browser launched');page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(60000);
  page.on('pageerror',e=>result.errors.push(e.message));
  await page.addInitScript(()=>{
   window.__spoken=[];speechSynthesis.speak=u=>window.__spoken.push({text:u.text,lang:u.lang});
   window.SpeechRecognition=class {constructor(){window.__recognition=this;}start(){}abort(){this.onerror?.({error:'aborted'});}};
  });
  progress('opening panel');await page.goto(process.env.SHOWROOM_URL,{waitUntil:'domcontentloaded'});
  const gallery=page.frameLocator('#showroom3d');
  await gallery.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
  await gallery.locator('#quality').selectOption('low');await gallery.locator('canvas').evaluate(el=>el.style.display='none');result.softwareRenderingPausedDuringControls=true;progress('gallery ready');console.log(await page.evaluate(()=>({language:latestState?.language,previousRun,error:document.getElementById('error').textContent,voiceErrorElement:!!document.getElementById('topVoiceError')})));for(const language of ['cs','en']){
   await page.locator('#language').selectOption(language);
   await page.waitForFunction(l=>latestState?.language===l,language);
   assert.equal(await page.locator('html').getAttribute('lang'),language);
   await gallery.locator('html').filter({has:gallery.locator('body')}).waitFor();
   await page.waitForFunction(l=>document.getElementById('showroom3d').contentDocument?.documentElement.lang===l,language);
   for(const car of ['tiggo4','tiggo7','tiggo8']){
    progress(language+' '+car+' start');await page.waitForFunction(()=>latestState?.ready_for_visit);
    await page.locator('#startVisit').click();
    await page.waitForFunction(()=>latestState?.interactive.stage==='choose');
    await page.locator('#car').selectOption(car);
    await page.waitForFunction(c=>latestState?.interactive.stage==='offer'&&latestState.selected===c,car);
    progress(language+' '+car+' voice');await page.locator('#showVoice').click();
    assert.equal(await page.evaluate(()=>window.__recognition.lang),language==='cs'?'cs-CZ':'en-US');
    await page.evaluate(()=>window.__recognition.onresult({results:[[{transcript:latestState.language==='cs'?'ano':'yes'}]]}));
    await page.waitForFunction(()=>latestState?.interactive.stage==='escort');
    await page.locator('#stop').click();await page.waitForFunction(()=>latestState?.interactive.stage==='paused');
    assert.equal(await page.evaluate(()=>latestState.gesture),false);
    await page.locator('button[onclick="act(\'reset\')"]').click();
    await page.waitForFunction(()=>!latestState?.interactive.active&&latestState?.ready_for_visit);
    assert.equal(await page.evaluate(()=>latestState.language),language);
    result.scenarios.push({language,car,consent:true,physicalEscortStarted:true,stop:true,reset:true});
   }
   progress(language+' reception');await gallery.locator('button[data-view=humanoid]').click();
   await gallery.locator('#concierge-question').fill(language==='cs'?'Kolik stojí CHERY?':'How much does the CHERY cost?');
   await gallery.locator('#concierge-send').click();
   await gallery.locator('#concierge-answer').filter({hasText:language==='cs'?'ověřen':'verif'}).waitFor({timeout:15000});
   await gallery.locator('canvas').evaluate(el=>el.style.display='');await gallery.locator('button[data-view=salon]').click();
   await gallery.locator('canvas[data-transitioning="false"]').waitFor({timeout:30000});
   await page.locator('#showroom3d').evaluate(el=>el.scrollIntoView({behavior:'instant',block:'center'}));
   const box=await gallery.locator('#viewport').boundingBox();
   await page.screenshot({path:path.join(out,'bilingual-'+language+'.png'),clip:box,animations:'disabled',timeout:60000});
   await gallery.locator('canvas').evaluate(el=>el.style.display='none');
   assert((await gallery.locator('link[rel=stylesheet]').getAttribute('href')).includes('index-KaHz0SVI.css'));
  }
  progress('complete English browser visit');
  await page.waitForFunction(()=>latestState?.ready_for_visit);
  await page.locator('#startVisit').click();
  await page.waitForFunction(()=>latestState?.interactive.stage==='choose');
  await page.locator('#car').selectOption('tiggo4');
  await page.waitForFunction(()=>latestState?.interactive.stage==='offer');
  await page.locator('[data-choice=yes]').click();
  await page.waitForFunction(()=>latestState?.interactive.stage==='presentation',null,{timeout:180000});
  for(let part=0;part<2;part++){
    await page.waitForFunction(()=>!latestState?.gesture,null,{timeout:15000});
    await page.locator('[data-choice=continue]').click();
    await page.waitForFunction(expected=>latestState?.interactive.presentation_part===expected,part+1);
  }
  await page.locator('#text').fill('How much does the BMW cost?');await page.locator('form button').click();
  await page.locator('#log').filter({hasText:'verified current price'}).waitFor();
  await page.locator('#endVisit').click();
  await page.waitForFunction(()=>latestState?.ready_for_visit&&latestState?.interactive.stage==='completed'&&latestState?.language==='cs',null,{timeout:240000});
  assert(!(await page.locator('#log').textContent()).includes('How much'));
  result.completeBrowserVisit=true;result.nextVisitorDefaultCzech=true;result.completedVisitClearsLog=true;
  assert.deepEqual(result.errors,[]);result.passed=true;
 } catch(error){if(page)result.failureSnapshot=await page.evaluate(()=>({stage:latestState?.interactive?.stage,error:document.getElementById('error').textContent,scrollY,voiceRect:document.getElementById('showVoice').getBoundingClientRect().toJSON(),barRect:document.getElementById('visitorBar').getBoundingClientRect().toJSON()}));throw error;} finally {fs.writeFileSync(path.join(out,'bilingual-result.json'),JSON.stringify(result,null,2));await browser.close();}
 console.log('Bilingual Chromium acceptance passed: both languages, three cars, speech locales, consent, Stop, reset, reception, unchanged stylesheet.');
})().catch(e=>{console.error(e);process.exitCode=1;});
