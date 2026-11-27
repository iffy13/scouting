const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const specs = JSON.parse(fs.readFileSync('specs.json')); const only = process.argv[2] ? new RegExp(process.argv[2]) : null;
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  fs.mkdirSync('out3/frames', { recursive: true }); let p = null, n = 0; const errs = [];
  const fresh = async () => { if (p) await p.close(); p = await b.newPage({ viewport: { width: 1280, height: 720 } }); p.on('pageerror', e => errs.push(e.message)); await p.goto('http://localhost:8765/thumb3.html'); await p.waitForFunction('window.READY === true'); };
  for (const s of specs) {
    if (only && !only.test(s.name)) continue;
    if (n++ % 4 === 0 || s.anim) await fresh();
    const t0 = Date.now();
    if (!s.anim) {
      const url = await p.evaluate(sp => window.renderSpec(sp), s.spec);
      fs.writeFileSync(`out3/${s.name}.jpg`, Buffer.from(url.split(',')[1], 'base64'));
    } else {
      await p.evaluate(sp => window.setupAnim(sp), s.spec); const F = 48;
      for (let f = 0; f < F; f++) { const url = await p.evaluate(t => window.animFrame(t), f / F); fs.writeFileSync(`out3/frames/${s.name}_${String(f).padStart(3, '0')}.jpg`, Buffer.from(url.split(',')[1], 'base64')); }
    }
    console.log(s.name, ((Date.now() - t0) / 1000).toFixed(1) + 's');
  }
  console.log('errors:', errs); await b.close();
})();
