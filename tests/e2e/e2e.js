// Browser end-to-end test. Usage: node tests/e2e/e2e.js [baseURL]
// Requires a running AeroFox server and Playwright (preinstalled or `npm i playwright`).
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://127.0.0.1:8000";
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

  await page.goto(BASE + "/");
  await page.waitForFunction(() => document.querySelector("#engineLabel").textContent !== "Checking engine…");
  check("home headline", (await page.textContent(".hero")).includes("What would you like to investigate"));
  check("four investigation cards", (await page.$$(".card")).length === 4);
  check("dataset count from API", (await page.textContent("#datasetCount")) === "24");
  check("snapshot label", /2026-11-14/.test(await page.textContent("#snapshot")));

  // card -> chart answer
  await page.click(".card >> nth=0");
  await page.waitForSelector(".msg-ai", { timeout: 30000 });
  await page.waitForSelector('.plot[data-rendered="true"]', { timeout: 15000 });
  check("Saffire card renders a chart", true);
  check("table rendered", (await page.$$(".msg-ai table.data")).length >= 1);
  check("evidence cards shown", (await page.$$(".msg-ai .ev")).length >= 1);

  // critical prompt: chart about main fire-safety factor for a lunar base
  await page.fill("#input", "Do a chart about the main factor on fire safety I should consider while projecting a lunar base.");
  await page.press("#input", "Enter");
  await page.waitForFunction(() => document.querySelectorAll(".msg-ai").length >= 2, null, { timeout: 30000 });
  const matrixCells = await page.$$eval(".msg-ai:last-of-type td[class^='lv-']", (c) => c.length);
  check("lunar-base chart request renders decision matrix", matrixCells > 10, `${matrixCells} coded cells`);

  // follow-up: atmosphere change with numbers -> chart
  await page.fill("#input", "We plan 8.2 psi and 34% oxygen. Now change the atmosphere and compare the results.");
  await page.press("#input", "Enter");
  await page.waitForFunction(() => document.querySelectorAll(".msg-ai").length >= 3, null, { timeout: 30000 });
  await page.waitForTimeout(800);
  check("follow-up renders atmosphere chart", (await page.$$('.msg-ai:last-of-type .plot[data-rendered="true"]')).length >= 1);
  check("project state shown as updated", /Updated project/.test(await page.textContent(".msg-ai:last-of-type .meta-row")));

  // CSV export link works
  const href = await page.getAttribute(".msg-ai:last-of-type .block-head a", "href");
  const csv = await page.evaluate(async (h) => (await fetch(h)).text(), href);
  check("CSV download returns data", csv.includes("source:") && csv.split("\n").length > 5);

  // evidence drawer
  await page.click(".msg-ai:last-of-type .ev >> nth=0");
  await page.waitForSelector("#evidenceDrawer:not([hidden]) .ev-detail");
  check("evidence drawer opens with source", (await page.textContent("#evidenceBody")).includes("Source"));
  await page.keyboard.press("Escape");

  // project inputs drawer shows stored values
  await page.click("#openProject");
  check("project drawer prefilled", (await page.inputValue('input[name="o2_pct"]')) === "34");
  await page.fill('input[name="materials"]', "Nomex, PMMA");
  await page.click("#projectForm button[type=submit]");
  await page.waitForFunction(() => /Saved/.test(document.querySelector("#projectMsg").textContent));
  check("project inputs saved", true);
  await page.keyboard.press("Escape");

  // Portuguese
  await page.fill("#input", "Explique o gráfico de forma mais simples");
  await page.press("#input", "Enter");
  await page.waitForFunction(() => document.querySelectorAll(".msg-ai").length >= 4, null, { timeout: 30000 });
  check("Portuguese simplification", /Em termos simples/.test(await page.textContent(".msg-ai:last-of-type .answer")));

  // library views
  for (const v of ["datasets", "findings", "references", "fields", "provenance"]) {
    await page.click(`[data-view="${v}"]`);
    await page.waitForFunction(() => !document.querySelector("#library").textContent.includes("Loading"), null, { timeout: 10000 });
    check(`library view: ${v}`, !(await page.$("#library .err")) && (await page.textContent("#library")).length > 200);
  }
  // history: new conversation then reopen the previous one
  await page.click("#newChat");
  check("new conversation resets thread", (await page.$$(".msg-ai")).length === 0);
  await page.click("#history button >> nth=0");
  await page.waitForFunction(() => document.querySelectorAll(".msg-user").length >= 1, null, { timeout: 10000 });
  check("previous conversation restored", (await page.$$(".msg-user")).length >= 3);

  // mobile layout: no horizontal overflow
  const m = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  await m.goto(BASE + "/");
  await m.waitForTimeout(600);
  const overflow = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("mobile: no horizontal scroll", overflow <= 0, `overflow ${overflow}px`);
  await m.click(".card >> nth=1");
  await m.waitForSelector(".msg-ai", { timeout: 30000 });
  const overflow2 = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("mobile: answer fits", overflow2 <= 0, `overflow ${overflow2}px`);
  if (process.env.SHOTS) {
    await m.screenshot({ path: process.env.SHOTS + "/mobile.png" });
    await page.click("#history button >> nth=0");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: process.env.SHOTS + "/desktop_conversation.png" });
  }
  check("no browser console errors", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} browser checks passed`);
  require("fs").writeFileSync(require("path").join(__dirname, "..", "..", "reports", "e2e_results.json"), JSON.stringify({ base: BASE, results }, null, 1));
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
