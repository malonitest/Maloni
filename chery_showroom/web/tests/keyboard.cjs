const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 assert(process.env.SHOWROOM_URL,'Set SHOWROOM_URL to runtime panel');
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||undefined});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const errors=[],actions=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(new URL(r.url()).pathname==='/action')actions.push(r.postData());});
  await page.goto(process.env.SHOWROOM_URL);
  assert((await page.locator('main').innerText()).includes('W / S'));
  await page.locator('#showroom3d').scrollIntoViewIfNeeded();
  const frame=page.frameLocator('#showroom3d');const canvas=frame.locator('canvas');
  await frame.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
  assert((await frame.locator('#camera-help').innerText()).includes('↑ / ↓'));
  const position=async()=>JSON.parse(await canvas.getAttribute('data-position'));
  const settled=()=>frame.locator('canvas[data-transitioning=false]').waitFor();
  const hold=async(key,ms=350)=>{await page.keyboard.down(key);await page.waitForTimeout(ms);await page.keyboard.up(key);await page.waitForTimeout(80);};
  // Axis assertions use a known forward-facing preset, independent of the opening composition.
  await frame.locator('button[data-view=entrance]').click();await settled();
  await canvas.focus();
  for(const [key,axis,sign] of [['ArrowUp',1,1],['ArrowDown',1,-1],['ArrowLeft',0,-1],['ArrowRight',0,1],['w',2,-1],['s',2,1]]){
   const before=await position();await hold(key);const after=await position();
   assert((after[axis]-before[axis])*sign>.15,`${key} must translate camera`);
   await page.waitForTimeout(200);const stopped=await position();
   assert(Math.hypot(...after.map((x,i)=>x-stopped[i]))<.001,'Keyup stops movement');
  }
  assert((await frame.locator('#camera-help').innerText()).includes('A / D'));
  assert((await page.locator('main').innerText()).includes('A / D'));
  const direction=async()=>JSON.parse(await canvas.getAttribute('data-direction'));
  for(const [key,sign] of [['a',-1],['d',1]]){
   const origin=await position(),before=await direction();await hold(key);const after=await direction();
   assert((after[0]-before[0])*sign>.15,`${key} must turn in the requested direction`);
   const stationary=await position();assert(Math.hypot(...origin.map((x,i)=>x-stationary[i]))<.001,'A/D must rotate in place');
   await page.waitForTimeout(200);assert.deepEqual(await direction(),after,'Keyup stops rotation');
  }
  const cameraFrame=page.frames().find(f=>f.url().includes('/web/'));
  const scroll=await page.evaluate(()=>scrollY);await hold('ArrowDown');assert.equal(await page.evaluate(()=>scrollY),scroll,'Focused arrows must not scroll dashboard');
  await page.keyboard.down('w');await page.waitForTimeout(100);await frame.locator('#quality').focus();await page.keyboard.up('w');
  const blurred=await position();await page.waitForTimeout(250);assert.deepEqual(await position(),blurred,'Blur clears held movement');
  await hold('ArrowUp');assert.deepEqual(await position(),blurred,'Select keys must not control camera');
  await frame.locator('button[data-view=reception]').click();await canvas.focus();await hold('ArrowRight',100);
  assert.equal(await canvas.getAttribute('data-transitioning'),'false','Keyboard cancels transition');
  await frame.locator('button[data-view=entrance]').click();await settled();await canvas.focus();
  // Bounded movement and reset through an existing preset.
  await hold('ArrowDown',1500);assert((await position())[1]>=.4);
  await hold('s',700);assert((await position())[2]<=6.1);
  await frame.locator('button[data-view=entrance]').click();await settled();
  await frame.locator('#settings summary').click();await frame.locator('#benchmark').click();await canvas.focus();await hold('w',100);
  assert((await frame.locator('#status').innerText()).includes('cancelled'),'Keyboard cancels benchmark');
  await frame.locator('#settings summary').click();
  await page.setViewportSize({width:390,height:844});
  assert(await frame.locator('#camera-help').isVisible());
  assert(await cameraFrame.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(actions,[],'3D keyboard must never send robot commands');assert.deepEqual(errors,[]);
  console.log('PASS: eight camera keys including in-place A/D yaw, keyup/blur, focus isolation, no dashboard scrolling, bounds, transition/benchmark cancellation, mobile help, no robot commands');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
