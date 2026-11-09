// Only public graphics routes are accessed; simulation commands are never sent.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const base = process.env.SHOWROOM_URL;
  assert(base, 'Set SHOWROOM_URL to the local showroom URL');
  const output = path.resolve(process.env.REVIEW_OUTPUT || '../assets/review/realism/after');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_EXECUTABLE || undefined,
    args: process.env.SOFTWARE_WEBGL ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : []
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    const errors = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && /WebGLProgram|shader error|INVALID_FRAMEBUFFER/i.test(m.text())) errors.push(m.text()); });
    page.on('request', r => { if (new URL(r.url()).origin !== new URL(base).origin) external.push(r.url()); });
    await page.goto(new URL('/web/', base).href);
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Ready'), null, { timeout: 180000 });
    const settled = () => page.waitForFunction(() => document.querySelector('canvas').dataset.transitioning === 'false', null, { timeout: 30000 });
    for (const view of ['front', 'side', 'whole']) {
      await page.locator(`button[data-view=${view}]`).first().click(); await settled();
      await page.screenshot({ path: path.join(output, view + '.png') });
    }
    assert.equal(await page.locator('#vehicle option').count(), 3);
    for (const id of ['tiggo4', 'tiggo7', 'tiggo8']) {
      await page.locator('#vehicle').selectOption(id); await settled();
      await page.screenshot({ path: path.join(output, id + '.png') });
    }
    for (const view of ['overview', 'salon', 'entrance', 'reception', 'lounge', 'staff', 'humanoid']) {
      await page.locator(`button[data-view=${view}]`).click(); await settled();
      const cutaway = view === 'overview';
      assert.equal(await page.locator('canvas').getAttribute('data-cutaway'), String(cutaway));
      assert.equal(await page.locator('canvas').getAttribute('data-facade-visible'), String(!cutaway));
      assert.equal(await page.locator('canvas').getAttribute('data-ceiling-visible'), String(!cutaway));
      await page.screenshot({ path: path.join(output, view + '.png') });
    }
    // Pointer input cancels a transition immediately; it must not resume after release.
    await page.locator('button[data-view=side]').click();
    await page.mouse.move(550, 180); await page.mouse.down(); await page.mouse.move(600, 200, { steps: 3 });
    assert.equal(await page.locator('canvas').getAttribute('data-transitioning'), 'false');
    await page.mouse.up();
    for (let i = 0; i < 5; i++) {
      await page.mouse.move(700, 160); await page.mouse.down(); await page.mouse.move(180, 380, { steps: 5 }); await page.mouse.up();
      await page.mouse.wheel(0, -350);
    }
    const position = JSON.parse(await page.locator('canvas').getAttribute('data-position'));
    assert(position[0] >= -8.65 && position[0] <= 8.65 && position[1] >= .4 && position[1] <= 4.45 && position[2] >= -6.1 && position[2] <= 6.1, 'Camera must remain inside building');
    const surfaces = JSON.parse(await page.locator('canvas').getAttribute('data-materials'));
    for (const vehicle of ['tiggo4', 'tiggo7', 'tiggo8']) for (const role of ['paint', 'glass', 'rubber', 'chrome']) {
      assert(surfaces[vehicle][role] > 0, `${vehicle} must contain ${role} triangles`);
    }
    const employee = JSON.parse(await page.locator('canvas').getAttribute('data-customer'));
    assert.equal(employee.role, 'customer');
    assert(employee.meshCount >= 8 && employee.texturedMeshes >= 8 && employee.triangles > 100000, 'Employee must be the detailed textured human asset');
    assert(Math.abs(employee.bounds[0][2]) < .01 && Math.abs(employee.bounds[1][2] - 1.68) < .01, 'Employee stands on the floor at adult scale');
    assert(employee.bounds[1][1] < -3.25, 'Customer is in front of the reception counter');
    assert(employee.bounds[0][0] > -3.65 && employee.bounds[1][0] < -.75, 'Employee aligns with reception counter');
    assert.equal(await page.locator('canvas').getAttribute('data-ambient-occlusion'), 'false');
    await page.locator('#quality').selectOption('high');
    await page.locator('button[data-view=staff]').click(); await settled();
    assert.equal(await page.locator('canvas').getAttribute('data-ambient-occlusion'), 'true');
    await page.screenshot({ path: path.join(output, 'staff-high.png') });
    await page.locator('#settings summary').click();
    await page.locator('#benchmarkMode').selectOption('motion');
    await page.locator('#benchmark').click();
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Benchmark:'));
    await page.locator('button[data-view=reception]').click(); await settled();
    assert((await page.locator('#status').textContent()).includes('cancelled'), 'Camera action cancels benchmark');
    await page.locator('#settings summary').click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('button[data-view=entrance]').click(); await settled();
    await page.screenshot({ path: path.join(output, 'mobile-entrance.png') });
    await page.locator('button[data-view=staff]').click(); await settled();
    await page.screenshot({ path: path.join(output, 'mobile-staff.png') });
    assert(await page.locator('#fallback').isVisible());
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    await page.evaluate(() => document.querySelector('canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('lost'));
    await page.route('**/graphics/chery.glb', route => route.fulfill({ status: 404, body: 'missing' }));
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Could not'), null, { timeout: 180000 });
    await page.unroute('**/graphics/chery.glb');
    await page.route('**/graphics/staff/receptionist.glb', route => route.fulfill({ status: 404, body: 'missing employee' }));
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Could not'), null, { timeout: 60000 });
    await page.unroute('**/graphics/staff/receptionist.glb');
    // Furniture failure also has to remain a recoverable graphics-only error.
    await page.route('**/graphics/furniture/modern_arm_chair_01.glb', route => route.fulfill({ status: 404, body: 'missing' }));
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Could not'), null, { timeout: 60000 });
    const noGL = await browser.newPage();
    await noGL.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type, ...args) { return type === 'webgl2' ? null : original.call(this, type, ...args); };
    });
    await noGL.goto(new URL('/web/', base).href);
    await noGL.waitForFunction(() => document.querySelector('#status').textContent.includes('Could not'));
    console.log('PASS: gallery/PBR, employee placement/scale/textures, all cameras/cutaway/bounds, high AO/AA, benchmark cancellation, mobile, local requests, WebGL/asset failures');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
