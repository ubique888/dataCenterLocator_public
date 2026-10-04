import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const browserDir = path.resolve(here, "..");
const outputDir = path.join(browserDir, ".qa", "visual-review");
const port = Number(process.env.PRESENTATION_PORT || 4173);
const baseUrl = process.env.PRESENTATION_URL || `http://127.0.0.1:${port}/presentation/browser/`;

async function loadPlaywright() {
  if (process.env.PLAYWRIGHT_MODULE) {
    return import(pathToFileURL(path.resolve(process.env.PLAYWRIGHT_MODULE)).href);
  }
  try {
    return await import("playwright");
  } catch {
    const require = createRequire(import.meta.url);
    try {
      return await import(pathToFileURL(require.resolve("playwright")).href);
    } catch {
      throw new Error("Playwright is not available. Install it or set PLAYWRIGHT_MODULE to its index.mjs entry.");
    }
  }
}

const { chromium } = await loadPlaywright();
await fs.mkdir(outputDir, { recursive: true });

let browser;
try {
  browser = await chromium.launch({
    headless: process.env.HEADLESS !== "0",
    ...(process.env.BROWSER_CHANNEL === "" ? {} : { channel: process.env.BROWSER_CHANNEL || "chrome" })
  });
} catch (error) {
  if (process.env.BROWSER_CHANNEL) throw error;
  browser = await chromium.launch({ headless: process.env.HEADLESS !== "0" });
}

const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  screen: { width: 1280, height: 720 },
  deviceScaleFactor: 1
});
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(error.stack || error.message));
const wait = (duration = 450) => page.waitForTimeout(duration);
const slide = (index) => page.evaluate((target) => Reveal.slide(target), index);
const save = async (name, duration = 450) => {
  await wait(duration);
  const destination = path.join(outputDir, `${name}.png`);
  await page.screenshot({ path: destination });
  console.log(destination);
};

try {
  const response = await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  if (!response?.ok()) throw new Error(`Deck server returned HTTP ${response?.status() ?? "no response"}: ${baseUrl}`);
  await page.waitForSelector(".reveal.ready .slides section.present", { timeout: 30000 });

  await slide(0);
  const speakerPopup = page.waitForEvent("popup", { timeout: 6000 }).catch(() => null);
  await page.keyboard.press("s");
  const speakerPage = await speakerPopup;
  if (!speakerPage) throw new Error("The reveal.js speaker view did not open on S.");
  await speakerPage.waitForLoadState("domcontentloaded", { timeout: 15000 });
  await speakerPage.waitForFunction(
    () => document.body.innerText.includes("The obvious answer for a data center"),
    null,
    { timeout: 15000 }
  );
  console.log("Speaker view verified: slide 1 notes are visible.");
  await speakerPage.close();
  await page.bringToFront();

  await slide(0); await save("01-opening");
  await slide(1); await save("02-density");
  await slide(2); await save("03-six-systems");
  await slide(3); await save("04a-funnel-source");
  await page.keyboard.press("ArrowRight"); await save("04b-funnel-filter");
  await page.keyboard.press("ArrowRight"); await save("04c-funnel-candidates");
  await page.keyboard.press("ArrowRight"); await save("04d-funnel-axes");
  await slide(4); await save("05-two-axis-chart");
  await slide(5); await save("06-site-explorer", 1200);

  const siteFrame = page.frame({ url: /infrastructure_inheritance_symbiosis\.html/ });
  if (siteFrame) {
    const formerOnly = siteFrame.locator("#former-only");
    if (await formerOnly.count()) {
      await formerOnly.click(); await save("06a-site-filter-on", 700);
      await formerOnly.click(); await save("06-site-explorer", 700);
    }
  }

  await slide(6); await save("07a-connectivity-map", 1200);
  const connectivityFrame = page.frame({ url: /power_connectivity_preview\.html/ });
  if (connectivityFrame) {
    for (const view of ["compare", "table", "map"]) {
      const tab = connectivityFrame.locator(`.connectivity-view-tab[data-view="${view}"]`).first();
      if (await tab.count()) {
        await tab.click({ timeout: 5000 });
        await save(`07-${view}`, 700);
      }
    }
  }
  await page.locator("#connectivity-demo [data-return-to-story]").click();
  await page.waitForFunction(() => location.hash.endsWith("/candidate-chart"));
  await save("07d-return-to-chart");

  await slide(7); await save("08-astoria-diligence");
  await slide(8); await save("09-conditional-roadmap");
} finally {
  await context.close();
  await browser.close();
}

if (pageErrors.length) {
  console.error("Browser page errors:");
  for (const error of pageErrors) console.error(`- ${error}`);
  process.exitCode = 1;
}
