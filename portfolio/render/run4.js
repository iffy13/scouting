const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [name, specJson, frames, every] = process.argv.slice(2); const spec = JSON.parse(specJson); const F = +frames, step = +(every || 1);
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://localhost:8765/anim4.html'); await p.waitForFunction('window.READY === true');
  await p.evaluate(sp => window.setupAnim(sp), spec);
  fs.mkdirSync(`out4/${name}`, { recursive: true }); const t0 = Date.now();
  for (let f = 0; f < F; f += step) { const url = await p.evaluate(t => window.animFrame(t), f / F); fs.writeFileSync(`out4/${name}/${String(f).padStart(4, '0')}.jpg`, Buffer.from(url.split(',')[1], 'base64')); }
  console.log(name, 'done in', ((Date.now() - t0) / 1000).toFixed(0) + 's', 'errors', errs); await b.close();
})();
