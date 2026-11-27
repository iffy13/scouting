const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  const scenes = (process.argv[2] || 'lava,hardcore,secret,server').split(',');
  for (const s of scenes) for (const mode of ['after', 'before']) {
    await p.goto(`http://localhost:8765/scene.html?scene=${s}&mode=${mode}`);
    await p.waitForFunction('window.READY === true', null, { timeout: 120000 });
    await p.waitForTimeout(300);
    require('fs').mkdirSync('out', { recursive: true }); await p.locator('#frame').screenshot({ path: `out/${s}_${mode}.png` });
    console.log('rendered', s, mode);
  }
  console.log('errors:', errs);
  await b.close();
})();
