// Run using the installed Windows node.exe, not Linux Node. An isolated temporary
// Chrome profile is created/removed by Playwright; no personal browser state is used.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  assert.equal(process.platform, 'win32', 'Use Windows node.exe for a real Windows GPU measurement');
  const captureOnly = process.argv.includes('--capture-only');
  const base = process.env.SHOWROOM_URL || process.argv.find(arg => arg.startsWith('--url='))?.slice(6) || 'http://127.0.0.1:8768';
  const output = path.resolve(process.env.REVIEW_OUTPUT || path.join(__dirname, '../../assets/review/realism/windows'));
  const benchmarkView = process.env.BENCHMARK_VIEW || 'overview';
  assert(['overview', 'salon'].includes(benchmarkView), 'Choose overview or salon for the performance view');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true,
    args: ['--use-angle=d3d11', '--no-first-run', '--no-default-browser-check'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, acceptDownloads: false });
    const page = await context.newPage();
    page.setDefaultTimeout(150000);
    const graphicsErrors = [];
    page.on('pageerror', error => graphicsErrors.push(error.message));
    page.on('console', message => { if (message.type() === 'error' && /WebGLProgram|shader error|INVALID_FRAMEBUFFER/i.test(message.text())) graphicsErrors.push(message.text()); });
    await page.goto(new URL('/web/', base).href);
    await page.waitForFunction(() => document.querySelector('#status')?.textContent.includes('Ready'), null, { timeout: 180000 });
    const gpu = await page.evaluate(() => {
      const gl = document.querySelector('canvas').getContext('webgl2');
      const info = gl.getExtension('WEBGL_debug_renderer_info');
      return { renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), vendor: info ? gl.getParameter(info.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR) };
    });
    console.log('WINDOWS GPU:', JSON.stringify(gpu));
    assert(/Intel|NVIDIA|AMD|Radeon/i.test(gpu.renderer) && !/swiftshader|llvmpipe|software|basic.?render/i.test(gpu.renderer), 'A software GPU is not valid target-device evidence');
    const browserSession = await browser.newBrowserCDPSession();
    const hardware = await browserSession.send('SystemInfo.getInfo');
    fs.writeFileSync(path.join(output, captureOnly ? 'gpu-visual.json' : 'gpu.json'), JSON.stringify({ gpu, devices: hardware.gpu.devices, driver: hardware.gpu.auxAttributes, browser: browser.version(), timestamp: new Date().toISOString() }, null, 2));
    const lightingSwitch = await page.evaluate(() => {
      const select = document.querySelector('#ambience'), result = {};
      for (const mode of ['evening', 'day']) {
        const start = performance.now(); select.value = mode; select.dispatchEvent(new Event('change', { bubbles: true }));
        result[mode] = performance.now() - start;
      }
      return result;
    });
    fs.writeFileSync(path.join(output, 'lighting-switch-ms.json'), JSON.stringify(lightingSwitch, null, 2));
    console.log('Synchronous lighting refresh (ms):', JSON.stringify(lightingSwitch));
    await page.locator('#quality').selectOption('low');
    await page.locator(`button[data-view=${benchmarkView}]`).click();
    await page.waitForFunction(() => document.querySelector('canvas').dataset.transitioning === 'false');
    await page.evaluate(() => {
      document.querySelector('#settings').open = true;
      const create = URL.createObjectURL.bind(URL);
      URL.createObjectURL = blob => { if (blob.type === 'application/json') blob.text().then(text => { window.__benchmarkResult = JSON.parse(text); }); return create(blob); };
      const click = HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click = function() { if (this.download !== 'showroom-benchmark.json') return click.call(this); };
    });
    for (const mode of captureOnly ? [] : ['static', 'motion']) {
      await page.locator('#benchmarkMode').selectOption(mode);
      await page.evaluate(() => { window.__benchmarkResult = null; });
      await page.locator('#benchmark').click();
      console.log('MEASURING', mode, '3 s warm-up + 60 s real elapsed time');
      await page.waitForFunction(() => window.__benchmarkResult !== null, null, { timeout: 100000, polling: 500 });
      const result = await page.evaluate(() => window.__benchmarkResult);
      assert.equal(result.ambience, 'day', 'Default performance evidence must identify the day atmosphere');
      result.gpu = gpu; result.simulationConcurrent = process.env.SIMULATION_ACTIVE === '1'; result.simulationContext = process.env.SIMULATION_CONTEXT || 'not specified'; result.platform = 'Windows native Chrome, headless, D3D11 hardware GPU'; result.timestamp = new Date().toISOString();
      fs.writeFileSync(path.join(output, mode + '.json'), JSON.stringify(result, null, 2));
      await page.screenshot({ path: path.join(output, mode + '.png') });
      console.log('RESULT', JSON.stringify(result));
    }
    await page.locator('#settings summary').click();
    await page.locator('button[data-view=reception]').click();
    await page.waitForFunction(() => document.querySelector('canvas').dataset.transitioning === 'false');
    await page.screenshot({ path: path.join(output, 'reception.png') });
    await page.locator('#quality').selectOption('high');
    await page.locator('button[data-view=staff]').click();
    await page.waitForFunction(() => document.querySelector('canvas').dataset.transitioning === 'false');
    await page.screenshot({ path: path.join(output, 'staff-high.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'mobile-staff.png') });
    assert.deepEqual(graphicsErrors, []);
    assert(!(await page.locator('#status').textContent()).match(/lost|Could not/));
    console.log('Windows hardware rendering: reception, high-quality AO/AA and mobile staff PASS.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
