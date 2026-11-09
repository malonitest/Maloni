const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const out=path.resolve('../../build/maloni120/browser');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message)});page.on('response',r=>{if(r.status()>=400)console.log('HTTP',r.status(),r.url())});
  await page.goto(process.env.SHOWROOM_URL,{waitUntil:'domcontentloaded'});
  const frame=page.frameLocator('#showroom3d');await frame.locator('button[data-view="humanoid"]:enabled').waitFor({timeout:120000});
  await frame.locator('canvas[data-backend="maloni120-planar"]').waitFor({timeout:30000});
  await frame.locator('button[data-view="humanoid"]').click();await page.waitForTimeout(2000);
  
  await page.evaluate(()=>act('chat','Kdo jsi?'));
  await page.waitForFunction(()=>document.getElementById('log').textContent.includes('virtuální MALONI Humanoid 120'));
  await page.evaluate(()=>act('greet'));await page.waitForTimeout(1200);
  
  await page.evaluate(()=>act('emergency_stop'));
  await page.waitForFunction(()=>document.getElementById('error').textContent.includes('Nouzové'));
  await page.evaluate(()=>act('reset'));await page.waitForFunction(()=>document.getElementById('error').textContent==='');
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:true,errors,checks:['gallery','maloni120-backend','identity-cs','greeting','emergency-stop','reset']},null,2));
  console.log('PASS: MALONI showroom browser, identity, gesture, emergency stop and reset');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
