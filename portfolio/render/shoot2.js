const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  require('fs').mkdirSync('out2', { recursive: true });
  for (const t of (process.argv[2] || 'vs,hardcore,timer,armor').split(',')) {
    await p.goto(`http://localhost:8765/thumb2.html?t=${t}`);
    await p.waitForFunction('window.READY === true', null, { timeout: 180000 });
    await p.locator('#out').screenshot({ path: `out2/${t}.png` }); console.log('rendered', t);
  }
  console.log('errors:', errs); await b.close();
})();
