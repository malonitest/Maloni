const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||undefined});
 try{
  assert(process.env.SHOWROOM_URL,'Set actual runtime panel URL');
  const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[],motion=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error'&&/WebGLProgram|shader error|INVALID_FRAMEBUFFER/.test(m.text()))errors.push(m.text());});
  page.on('request',r=>{if(new URL(r.url()).pathname==='/action')motion.push(r.postData());});
  // Capture the exact spoken reply without relying on installed voices or sound hardware.
  await page.addInitScript(()=>{
   window.__spoken=[];window.__speechLanguages=[];
   speechSynthesis.speak=u=>{window.__spoken.push(u.text);window.__speechLanguages.push(u.lang);};
   window.SpeechRecognition=class {start(){window.__recognitionLanguage=this.lang;}};
  });
  await page.goto(process.env.SHOWROOM_URL);await page.locator('#showroom3d').scrollIntoViewIfNeeded();
  const frame=page.frameLocator('#showroom3d');
  await frame.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.equal(await frame.locator('html').getAttribute('lang'),'en');
  await page.locator('#mic').click();
  assert.equal(await page.evaluate(()=>window.__recognitionLanguage),'en-US');
  const bounds=JSON.parse(await frame.locator('canvas').getAttribute('data-humanoid'));
  bounds.min={x:bounds.min[0],y:bounds.min[1],z:bounds.min[2]};bounds.max={x:bounds.max[0],y:bounds.max[1],z:bounds.max[2]};
  assert(Math.abs(bounds.min.z)<.01&&Math.abs(bounds.max.z-1.68)<.015,'G1 must stand on floor at customer height');
  assert(bounds.max.y < -1.0 && bounds.min.y > -1.875,'G1 stands behind worktop');
  const customer=JSON.parse(await frame.locator('canvas').getAttribute('data-customer'));
  assert.equal(customer.role,'customer');
  assert(customer.bounds[1][1]<-3.25,'Customer stands in front of counter');
  const customerX=(customer.bounds[0][0]+customer.bounds[1][0])/2;
  assert(Math.abs(customerX-(bounds.min.x+bounds.max.x)/2)<.02,'People stand opposite each other');
  assert(Math.abs(customer.bounds[1][2]-bounds.max.z)<.015,'People have equal height');
  const facing=JSON.parse(await frame.locator('canvas').getAttribute('data-reception-facing'));
  assert(facing.customer.reduce((sum,v,i)=>sum+v*facing.humanoid[i],0)<-.99,'People face each other');
  const details=JSON.parse(await frame.locator('canvas').getAttribute('data-humanoid-details'));
  assert(details.shells>0&&details.joints>0&&details.elastomers>0&&details.surfaceDetails>=3,'Humanoid has separate finishes and fitted sensor/fastener details');
  assert(bounds.min.x>-3.65&&bounds.max.x<-.75,'G1 is aligned with desk');
  await frame.locator('button[data-view=humanoid]').click();
  await frame.locator('canvas[data-transitioning=false]').waitFor();
  await frame.locator('#concierge-send').waitFor({state:'visible'});
  await page.locator('#voice').check();
  const question=frame.locator('#concierge-question'),answer=frame.locator('#concierge-answer');
  await question.fill('What colour is the CHERY?');
  await frame.locator('#concierge-send').click();
  await answer.filter({hasText:'CHERY'}).waitFor({timeout:15000});
  const actual=await answer.innerText();assert(actual.includes('teal')||actual.includes('dark'));
  await page.waitForFunction(text=>window.__spoken.includes(text),actual);
  assert((await page.evaluate(()=>window.__speechLanguages)).every(lang=>lang==='en-US'));
  assert(await frame.locator('#concierge-send').isEnabled());
  // Input W/A/S/D is text and must not change camera pose.
  const pose=await frame.locator('canvas').getAttribute('data-position');await question.fill('wasd');await page.waitForTimeout(100);
  assert.equal(await frame.locator('canvas').getAttribute('data-position'),pose);
  await question.fill('How much does the car cost?');await frame.locator('#concierge-send').click();
  await answer.filter({hasText:'verified'}).waitFor({timeout:15000});
  assert.deepEqual(motion,[],'Reception Q&A must never queue locomotion actions');
  const output=path.resolve(process.env.REVIEW_OUTPUT||path.join(__dirname,'../../assets/review/reception'));fs.mkdirSync(output,{recursive:true});
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(output,'dashboard-english.png')});
  await page.locator('#showroom3d').screenshot({path:path.join(output,'humanoid-desktop.png')});
  await frame.locator('button[data-view=reception]').click();await frame.locator('canvas[data-transitioning=false]').waitFor();
  await frame.locator('#concierge summary').click();
  await page.locator('#showroom3d').screenshot({path:path.join(output,'desk-desktop.png')});
  await frame.locator('#concierge summary').click();
  // Failed transport is explicit, recoverable, and never fabricates a reply.
  await page.route('**/reception/chat',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Conversation is temporarily unavailable.'})}));
  await question.fill('Hello');await frame.locator('#concierge-send').click();
  await answer.filter({hasText:'temporarily'}).waitFor();assert(await frame.locator('#concierge-send').isEnabled());
  await page.unroute('**/reception/chat');
  await page.setViewportSize({width:390,height:844});
  await page.locator('#showroom3d').scrollIntoViewIfNeeded();
  const child=page.frames().find(f=>f.url().includes('/web/'));
  await child.evaluate(()=>{document.querySelector('#concierge').open=true;});
  assert(await question.isVisible());assert(await child.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#showroom3d').screenshot({path:path.join(output,'humanoid-mobile.png')});
  assert.deepEqual(errors,[]);
  console.log('PASS: equal G1/customer height, opposing roles/facing, refined surfaces, real authenticated reply, spoken reply, no motion commands, input focus, error recovery, mobile');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
