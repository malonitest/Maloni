// Real rendered day/night transitions, including repeated static-probe refreshes.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  assert(process.env.SHOWROOM_URL, 'Set the real runtime SHOWROOM_URL');
  const output = path.resolve(process.env.REVIEW_OUTPUT || path.join(__dirname, '../../assets/review/gallery/atmospheres'));
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    const errors = [], actions = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && /WebGLProgram|shader error|INVALID_FRAMEBUFFER/i.test(m.text())) errors.push(m.text()); });
    page.on('request', r => {
      const url = new URL(r.url());
      if (url.pathname === '/action') actions.push(r.postData());
      if (url.origin !== new URL(process.env.SHOWROOM_URL).origin) external.push(r.url());
    });
    await page.goto(new URL('/web/', process.env.SHOWROOM_URL).href);
    await page.locator('#status').filter({ hasText: 'Ready' }).waitFor({ timeout: 180000 });
    const canvas = page.locator('canvas');
    const settle = () => page.locator('canvas[data-transitioning=false]').waitFor();
    const mode = async name => {
      await page.locator('#ambience').selectOption(name);
      await page.locator(`canvas[data-ambience=${name}]`).waitFor();
    };
    assert.equal(await canvas.getAttribute('data-ambience'), 'day');
    await page.locator('button[data-view=whole]').click(); await settle();
    const pose = await canvas.getAttribute('data-position');
    await canvas.screenshot({ path: path.join(output, 'day-original.png') });
    for (let i = 1; i <= 2; i++) {
      await mode('evening');
      assert.equal(await canvas.getAttribute('data-position'), pose, 'Lighting must preserve the current camera');
      assert.equal(await page.locator('#vehicle').inputValue(), 'tiggo8');
      await canvas.screenshot({ path: path.join(output, `evening-${i}.png`) });
      await mode('day');
      await canvas.screenshot({ path: path.join(output, `day-return-${i}.png`) });
    }
    await mode('evening');
    for (const view of ['overview', 'salon', 'entrance', 'reception', 'lounge', 'humanoid']) {
      await page.locator(`button[data-view=${view}]`).click(); await settle();
      // Close the conversation overlay to keep graphics comparable.
      await page.locator('#concierge').evaluate(e => { e.open = false; });
      await page.screenshot({ path: path.join(output, `evening-${view}.png`) });
    }
    await page.locator('#quality').selectOption('high');
    await page.locator('button[data-view=reception]').click(); await settle();
    assert.equal(await canvas.getAttribute('data-ambience'), 'evening');
    await page.screenshot({ path: path.join(output, 'evening-reception-high.png') });
    await page.locator('#quality').selectOption('low');
    await page.locator('#settings summary').click();
    await page.locator('#benchmark').click();
    await page.locator('#status').filter({ hasText: 'Benchmark:' }).waitFor();
    await mode('day');
    assert.match(await page.locator('#status').innerText(), /cancelled/);
    await page.locator('#settings summary').click();
    await page.setViewportSize({ width: 390, height: 844 });
    await mode('evening');
    assert(await page.locator('#ambience').isVisible());
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(output, 'evening-mobile.png') });
    assert.deepEqual(actions, []); assert.deepEqual(external, []); assert.deepEqual(errors, []);
    console.log('PASS: day/evening, repeated probes, preserved camera/car, all evening views, high quality, benchmark cancellation, mobile, local requests');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
