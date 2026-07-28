import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = "visual-check-screenshots";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const consoleErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(String(err)));

await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
await page.fill("#subdomain", "skillsverify-fixed");
await page.fill("#email", "skillsverify2@example.com");
await page.fill("#password", "VerifyPass123!");
await page.click('button[type="submit"]');
await page.waitForTimeout(1500);
console.log("URL after login attempt:", page.url());

// The access token lives in Zustand memory only, so a hard navigation
// (page.goto) loses the session — click the SPA's own nav links instead.
await page.click('a[href="/profile"]');
await page.waitForTimeout(800);
await page.screenshot({ path: `${outDir}/profile-page.png`, fullPage: true });

// Left Nav separator + rainbow header are both above the fold — a
// viewport screenshot (not fullPage) frames them tightly.
await page.screenshot({ path: `${outDir}/header-and-leftnav.png`, fullPage: false });

await browser.close();

console.log("Console errors:", consoleErrors.length ? consoleErrors : "none");
console.log("Screenshots written to", outDir);
