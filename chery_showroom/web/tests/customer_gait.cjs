const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const out=process.env.REVIEW_OUTPUT;fs.mkdirSync(out,{recursive:true});const result={passed:false,scenarios:[],errors:[],softwareRenderPausedDuringControl:true};
 const save=step=>{result.step=step;fs.writeFileSync(path.join(out,'customer-gait-result.json'),JSON.stringify(result,null,2));console.log(step);};
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(60000);page.on('pageerror',e=>result.errors.push(e.message));await page.addInitScript(()=>{window.__gaitTraffic=[];window.addEventListener('message',e=>{if(e.data?.type==='showroom-state'){window.__gaitTraffic.push({time:e.data.simulation?.sim_time,customer:e.data.simulation?.customer});if(window.__gaitTraffic.length>500)window.__gaitTraffic.shift();}})});save('loading original showroom');
  await page.goto(process.env.SHOWROOM_URL);const gallery=page.frameLocator('#showroom3d');await gallery.locator('#status').filter({hasText:'Ready'}).waitFor({timeout:180000});
  await gallery.locator('#quality').selectOption('low');const canvas=gallery.locator('canvas');await canvas.evaluate(e=>e.style.display='none');await page.waitForTimeout(500);
  const gait=()=>canvas.evaluate(e=>JSON.parse(e.dataset.customerGait));
  const waitGait=(predicate,arg,timeout=20000)=>page.waitForFunction(({predicate,arg})=>{const canvas=document.getElementById('showroom3d').contentDocument.querySelector('canvas');return canvas?.dataset.customerGait&&Function('g','arg','return ('+predicate+')(g,arg)')(JSON.parse(canvas.dataset.customerGait),arg);},{predicate:predicate.toString(),arg},{timeout,polling:50});
  await waitGait(g=>g.bones===15);const rest=await gait();assert(rest.restBoundsError<1e-5);assert(rest.maxWeightError<1e-6);result.rig=rest;
  save('reset while customer walking');await page.waitForFunction(()=>latestState.ready_for_visit&&Date.now()-last<400);await page.evaluate(async()=>{await fetch('/state',{headers:{'X-Showroom-Token':token}});await act('start_visit');});await waitGait(g=>g.distance>.05&&g.blend>.1);
  const oldRun=await page.evaluate(()=>latestState.run_id);await page.evaluate(()=>act('reset'));await page.waitForFunction(r=>latestState.run_id!==r&&latestState.ready_for_visit,oldRun);await waitGait((g,r)=>g.run_id!==r&&g.phase===0&&g.blend===0,oldRun);result.resetClearsGait=true;
  for(const car of ['tiggo4','tiggo7','tiggo8']){
   save(car+' arrival');await page.evaluate(()=>act('start_visit'));await waitGait(g=>g.distance>.05&&g.blend>.1);const arrival=await gait();
   await page.waitForFunction(()=>latestState.interactive.stage==='choose');await waitGait(g=>g.blend===0);
   // Use the same authenticated controller as the visitor UI, with an explicit model selection.
   await page.locator('#car').selectOption(car);await page.waitForFunction(c=>latestState.interactive.stage==='offer'&&latestState.selected===c,car);
   await page.evaluate(()=>send('yes'));save(car+' physical escort');await waitGait((g,d)=>g.distance>d+.15&&g.blend>.7,arrival.distance,60000);
   if(car==='tiggo4'){
    await page.evaluate(()=>act('stop'));await page.waitForFunction(()=>latestState.interactive.stage==='paused');await waitGait(g=>g.paused);const stopped=await gait();await page.waitForTimeout(350);const frozen=await gait();assert.equal(frozen.phase,stopped.phase);assert.deepEqual(frozen.jointRotations,stopped.jointRotations);result.stopFreezesPose=true;
    const access=await page.evaluate(()=>token);const heartbeat=setInterval(()=>{fetch(process.env.SHOWROOM_URL+'/state',{headers:{'X-Showroom-Token':access}}).catch(()=>{});},100);
    try{await gallery.locator('button[data-view=reception]').click();await canvas.evaluate(e=>e.style.display='');await gallery.locator('canvas[data-transitioning="false"]').waitFor();await page.locator('#showroom3d').scrollIntoViewIfNeeded();const box=await gallery.locator('#viewport').boundingBox();await page.screenshot({path:path.join(out,'customer-gait-paused.png'),clip:box,timeout:60000});await canvas.evaluate(e=>e.style.display='none');}finally{clearInterval(heartbeat);}
    result.snapshotHasIndependentClient=true;
    await page.evaluate(()=>act('interactive_continue'));await waitGait((g,d)=>!g.paused&&g.distance>d+.05,stopped.distance,60000);result.resumeAdvancesPose=true;
   }
   await page.waitForFunction(()=>latestState.interactive.stage==='presentation',null,{timeout:240000});await waitGait(g=>g.blend===0,null,30000);const waiting=await gait();
   await page.evaluate(()=>send('How much does this car cost?'));await page.waitForFunction(()=>latestState.interactive.stage==='questions');
   await page.evaluate(()=>act('end_visit'));save(car+' departure');await waitGait((g,d)=>g.distance>d+.05&&g.blend>.1,waiting.distance,30000);
   await page.waitForFunction(()=>latestState.ready_for_visit&&latestState.interactive.stage==='completed',null,{timeout:240000});
   result.scenarios.push({car,arrival:true,escort:true,waiting:true,question:true,departure:true,physicalReturn:true});save(car+' complete');
  }
  await gallery.locator('button[data-view=reception]').click();await canvas.evaluate(e=>e.style.display='');await gallery.locator('canvas[data-transitioning="false"]').waitFor();await page.locator('#showroom3d').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'customer-gait-idle.png'),clip:await gallery.locator('#viewport').boundingBox(),timeout:60000});
  assert.equal(result.errors.length,0);result.passed=true;save('passed');
 }catch(error){result.failure=String(error);if(page)result.state=await page.evaluate(()=>({phase:latestState?.phase,interactive:latestState?.interactive,error:latestState?.error,traffic:document.getElementById('showroom3d').contentWindow.__gaitTraffic,lastPollAge:Date.now()-last,gait:document.getElementById('showroom3d').contentDocument.querySelector('canvas').dataset.customerGait}));throw error;}
 finally{fs.writeFileSync(path.join(out,'customer-gait-result.json'),JSON.stringify(result,null,2));await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
