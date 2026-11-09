// Covers updated frontend with an older running backend and a genuinely missing avatar.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||undefined});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[],failed=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push(r.url());});
  page.on('request',r=>requests.push(new URL(r.url()).pathname));
  if(!process.env.LEGACY_SERVER)await page.route('**/state',async route=>{
   const response=await route.fetch(),data=await response.json();delete data.language;
   data.message='Starý český server';data.error='Přerušeno spojení';
   await route.fulfill({response,json:data});
  });
  await page.goto(process.env.SHOWROOM_URL);await page.locator('#showroom3d').scrollIntoViewIfNeeded();
  const frame=page.frameLocator('#showroom3d');
  const ready=()=>frame.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
  await ready();
  assert.notEqual(await frame.locator('canvas').getAttribute('data-humanoid'),'null');
  await frame.locator('button[data-view=humanoid]').click();
  await frame.locator('#concierge-answer').filter({hasText:'Restart the showroom'}).waitFor();
  assert(await frame.locator('#concierge-send').isDisabled());
  assert(!(await page.locator('#log').innerText()).includes('Starý český server'));
  assert((await page.locator('#error').innerText()).includes('Restart the showroom'));
  assert(requests.includes('/web/models/g1-reception.glb'));
  assert(!requests.includes('/graphics/staff/g1-reception.glb'),'Bundled model must not depend on a newly added alias');
  assert.deepEqual(failed,[],'Old backend must render model without 404s');
  if(process.env.PANEL_SCREENSHOT)await page.locator('#showroom3d').screenshot({path:process.env.PANEL_SCREENSHOT});
  await page.route('**/web/models/g1-reception.glb',r=>r.fulfill({status:404,body:'missing model'}));
  await page.reload();await page.locator('#showroom3d').scrollIntoViewIfNeeded();await ready();
  await frame.locator('#status').filter({hasText:'The humanoid model is unavailable'}).waitFor();
  assert.equal(await frame.locator('#vehicle option').count(),3);
  assert.equal(await frame.locator('canvas').getAttribute('data-humanoid'),'null');
  assert(await frame.locator('button[data-view=humanoid]').isDisabled());
  await frame.locator('button[data-view=side]').click();await frame.locator('canvas[data-transitioning=false]').waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS: old backend compatibility, no model alias 404, explicit restart notice, missing G1 preserves showroom/cameras');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
