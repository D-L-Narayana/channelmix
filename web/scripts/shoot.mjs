import { chromium } from '@playwright/test'
const [,, url, out, w, h, extra] = process.argv
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1, colorScheme: 'dark' })
const page = await ctx.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
if (extra) { await eval('(async()=>{' + extra + '})()') ; await page.waitForTimeout(1200) }
await page.screenshot({ path: out, fullPage: true })
console.log('saved', out, 'errors:', errors.length ? errors : 'none')
await browser.close()
