const { chromium } = require('playwright');
const path = require('path');
const [,, html, outDir, qs=''] = process.argv;
(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await b.newPage({ viewport:{width:1920,height:1080}, deviceScaleFactor:1 });
  await p.goto('file://' + path.resolve(html) + (qs ? '?' + qs : ''));
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(500);
  const n = await p.locator('section.slide').count();
  for (let i = 0; i < n; i++) await p.locator('section.slide').nth(i).screenshot({ path: `${outDir}/slide-${i+1}.png` });
  await p.pdf({ path: `${outDir}/EMBER-slides.pdf`, width: '1920px', height: '1080px', printBackground: true });
  console.log('rendered', n); await b.close();
})();
