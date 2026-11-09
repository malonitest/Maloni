const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:process.env.SOFTWARE_WEBGL?['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[]});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[],failed=[],loaded=new Set();
  page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure().errorText}));page.on('response',r=>{if(r.ok())loaded.add(r.url());if(r.status()>=400) errors.push(r.status()+' '+r.url());});
  assert(process.env.SHOWROOM_URL, 'Set SHOWROOM_URL to the actual runtime panel URL');
  await page.goto(process.env.SHOWROOM_URL);
  await page.locator('#showroom3d').scrollIntoViewIfNeeded();
  const frame=page.frameLocator('#showroom3d');
  await frame.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
  await page.waitForFunction(()=>document.querySelector('#state').textContent.includes('position'),null,{timeout:20000});
  await frame.locator('button[data-view=reception]').click();
  await frame.locator('canvas[data-transitioning=false]').waitFor({timeout:30000});
  await page.locator('#showSimulation').click();
  await page.waitForFunction(()=>document.querySelector('#showroom3d').style.display==='none');
  await page.waitForFunction(()=>latestState?.camera_ready===true,null,{timeout:15000});
  await page.waitForFunction(()=>document.querySelector('#camera').naturalWidth>0,null,{timeout:15000});
  await page.locator('#show3d').click();
  await page.waitForFunction(()=>document.querySelector('#showroom3d').style.display==='block');
  if(process.env.PANEL_SCREENSHOT)await page.screenshot({path:process.env.PANEL_SCREENSHOT});
  for(const failure of failed){
   // Browser retries/cancelled duplicate loads are acceptable only when the same asset succeeds.
   if(failure.error!=='net::ERR_ABORTED'||!loaded.has(failure.url))errors.push(failure.url+': '+failure.error);
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  console.log('PASS: real simulation server, embedded 3D, reception camera, heartbeat state, no HTTP/JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
