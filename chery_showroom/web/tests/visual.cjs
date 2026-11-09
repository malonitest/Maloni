// Capture reproducible before/after views against the real runtime server.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.SHOWROOM_URL||process.argv.find(x=>x.startsWith('--url='))?.slice(6);
 const output=path.resolve(process.env.REVIEW_OUTPUT||path.join(__dirname,'../../assets/review/daylight/after'));
 assert(base,'Set SHOWROOM_URL or --url=');fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':undefined),args:process.platform==='win32'?['--use-angle=d3d11']:process.env.SOFTWARE_WEBGL?['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[]});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error'&&/WebGLProgram|shader error|INVALID_FRAMEBUFFER/i.test(m.text()))errors.push(m.text());});
  await page.goto(new URL('/web/',base).href);
  await page.waitForFunction(()=>document.querySelector('#status')?.textContent.includes('Ready'),null,{timeout:180000});
  const settle=()=>page.waitForFunction(()=>document.querySelector('canvas').dataset.transitioning==='false');
  for(const quality of ['low','high']){
   await page.locator('#quality').selectOption(quality);
   for(const view of ['overview','salon','entrance','reception','lounge','staff']){
    await page.locator(`button[data-view=${view}]`).click();await settle();
    await page.screenshot({path:path.join(output,`${view}-${quality}.png`)});
   }
   for(const vehicle of ['tiggo4','tiggo7','tiggo8']){
    await page.locator('#vehicle').selectOption(vehicle);await settle();
    await page.screenshot({path:path.join(output,`${vehicle}-${quality}.png`)});
   }
  }
  await page.locator('#quality').selectOption('low');await page.setViewportSize({width:390,height:844});
  for(const view of ['entrance','staff']){
   await page.locator(`button[data-view=${view}]`).click();await settle();
   await page.screenshot({path:path.join(output,`mobile-${view}.png`)});
  }
  assert.deepEqual(errors,[]);console.log('Visual captures PASS:',output);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
