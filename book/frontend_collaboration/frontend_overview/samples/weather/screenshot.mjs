// 天气查询页截图脚本：本地用 Playwright 打开样例页面，产出 figs/ 下的截图。
// 用法：npm install && npm run screenshot
import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const url = 'file://' + path.join(__dirname, 'index.html');
const outDir = path.join(__dirname, '..', '..', 'figs');
const outFile = path.join(outDir, 'frontend_overview_weather.png');

fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 720, height: 520 } });
await page.goto(url, { waitUntil: 'load' });
await page.waitForSelector('#weather-card');
await page.screenshot({ path: outFile });
await browser.close();

console.log('screenshot saved to', outFile);