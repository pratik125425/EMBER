const { chromium } = require('playwright');
const path = require('path');
const [,, html, outDir, qs=''] = process.argv;
(async () => {
  const b = await chromium.launch({ channel: 'chrome', args: ['--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport:{width:1920,height:1080}, acceptDownloads: true });
  const p = await ctx.newPage();
  p.on('console', m => console.log('page:', m.text()));
  await p.goto('file://' + path.resolve(html) + (qs ? '?' + qs : ''));
  await p.evaluate(() => window.ready);
  // stills for checking subtitles
  for (const t of [1.5, 5, 9.7, 14.5, 19, 23.5, 27.5]) {
    await p.evaluate(t => window.preview(t), t);
    await p.screenshot({ path: `${outDir}/still-${t}.png` });
  }
  const dl = p.waitForEvent('download', { timeout: 120000 });
  const mime = await p.evaluate(() => window.record());
  const d = await dl; const name = d.suggestedFilename();
  await d.saveAs(path.join(outDir, name));
  console.log('saved', name, mime);
  await b.close();
})();
