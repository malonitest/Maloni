// Exercise the existing gallery and dashboard on the real native backend.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const base = process.env.SHOWROOM_URL;
  assert(base, 'Set SHOWROOM_URL');
  const out = path.resolve(process.env.REVIEW_OUTPUT || '../../../build/showroom-native/browser');
  fs.mkdirSync(out, {recursive:true});
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:false,status:'running'}));
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,
    args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    await page.addInitScript(()=>{
      window.__spoken=[];
      speechSynthesis.speak=utterance=>window.__spoken.push(utterance.text);
      window.SpeechRecognition=class {
        constructor(){window.__recognition=this;}
        start(){}
        abort(){this.onerror?.({error:'aborted'});}
      };
    });
    const actions=[];
    page.on('request',request=>{if(new URL(request.url()).pathname==='/action')actions.push(request.postData());});
    const errors=[],external=[],failed=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(new URL(r.url()).origin!==new URL(base).origin)external.push(r.url());});
    page.on('response',r=>{if(r.status()>=400)failed.push([r.status(),r.url()]);});
    await page.goto(base,{waitUntil:'domcontentloaded'});
    const gallery=page.frameLocator('#showroom3d');
    async function captureGallery(file) {
      await page.locator('#showroom3d').evaluate(el=>el.scrollIntoView({behavior:'instant',block:'center'}));
      const box=await gallery.locator('#viewport').boundingBox();
      assert(box&&box.width>0&&box.height>0,'Gallery has a visible viewport');
      await page.screenshot({path:path.join(out,file),clip:box,animations:'disabled'});
    }
    await gallery.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
    await gallery.locator('canvas[data-backend="maloni-native"]').waitFor({timeout:15000});
    const layout=await page.evaluate(async()=>await(await fetch('/graphics/layout.json')).json());
    const measured=JSON.parse(await gallery.locator('canvas').getAttribute('data-shared-scene'));
    for(const id of ['left_lounge_chair','right_lounge_chair','reception_counter','staff_desk','coffee_table','consultation_bench','tiggo4','tiggo7','tiggo8']) {
      assert(measured[id],id+' is bound to the shared scene');
      const resolve=key=>{const o=layout.scene.objects[key];if(!o.parent)return o.position;const parent=resolve(o.parent);return o.position.map((v,i)=>v+parent[i]);};
      resolve(id).forEach((v,i)=>assert(Math.abs(measured[id].position[i]-v)<1e-7,id+' rendered at shared coordinates'));
    }
    assert.equal(await gallery.locator('#vehicle option').count(),3);
    const names=await gallery.locator('#vehicle option').allTextContents();
    for(const name of ['BMW X1 2013','Volvo XC60 2023','CHERY Tiggo 8 Pro 2023'])assert(names.includes(name),name);
    assert((await gallery.locator('link[rel=stylesheet]').getAttribute('href')).includes('index-KaHz0SVI.css'),'Preserve original stylesheet');
    for(const id of ['tiggo4','tiggo7','tiggo8']){
      await gallery.locator('#vehicle').selectOption(id);
      await gallery.locator('canvas[data-transitioning="false"]').waitFor({timeout:30000});
      await captureGallery(id+'.png');
    }
    await gallery.locator('button[data-view=humanoid]').click();
    await gallery.locator('#concierge-send').waitFor({state:'visible'});
    await gallery.locator('#concierge-question').fill('How much does the CHERY cost?');
    await gallery.locator('#concierge-send').click();
    await gallery.locator('#concierge-answer').filter({hasText:/verif/i}).waitFor({timeout:15000});
    const reply=await gallery.locator('#concierge-answer').textContent();
    await gallery.locator('#concierge-question').fill('What is the length of Volvo XC60?');
    await gallery.locator('#concierge-send').click();
    await gallery.locator('#concierge-answer').filter({hasText:'4708'}).waitFor({timeout:15000});
    assert.match(await gallery.locator('#concierge-answer').textContent(),/NZ/);
    await page.evaluate(()=>{listen();window.__lateRecognition=window.__recognition;});
    await page.locator('#stop').click();
    const stoppedActions=actions.length;
    await page.evaluate(()=>window.__lateRecognition.onresult({results:[[{transcript:'Escort me to BMW X1'}]]}));
    await page.waitForTimeout(100);
    assert.equal(actions.length,stoppedActions,'Stop rejects late microphone results');
    await page.locator('#view').selectOption('robot');
    await gallery.locator('canvas[data-view="robot"]').waitFor({timeout:15000});
    await page.getByRole('button',{name:'3D showroom',exact:true}).click();
    await gallery.locator('button[data-view=salon]').click();
    await gallery.locator('canvas[data-transitioning="false"]').waitFor({timeout:30000});
    await captureGallery('existing-showroom.png');
    await page.getByRole('button',{name:'Reset',exact:true}).click();
    await gallery.locator('#concierge-answer').filter({hasText:/reset/i}).waitFor({timeout:15000});
    assert.deepEqual(errors,[],'No browser errors');
    assert.deepEqual(external,[],'All gallery assets remain local');
    assert.deepEqual(failed,[],'All resources and API requests succeed');
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:true,backend:'maloni-native',vehicles:names,reply,errors,external,failed,originalStylesheet:true,scopedCatalog:true,browserVoiceStop:true,audioTransport:'mocked browser recognition; no physical microphone or paid cloud call'},null,2));
    console.log('Native showroom browser acceptance passed: all cars, original design, live physics, reception chat, robot camera, reset.');
  } catch(error) {fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:false,status:'failed',error:String(error)}));throw error;} finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
