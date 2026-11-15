// Builds docs/AeroFox_Technical_Report.docx from the project's generated results.
// Usage: node scripts/build_report.js   (then convert to PDF with LibreOffice)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle,
  HeadingLevel, PageBreak, TabStopType, Footer, PageNumber, ShadingType, LevelFormat, TableOfContents,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const R = (p) => path.join(ROOT, p);
const findings = JSON.parse(fs.readFileSync(R("data/findings/findings.json"))).findings;
const F = Object.fromEntries(findings.map((f) => [f.id, f]));
const bench = JSON.parse(fs.readFileSync(R("reports/benchmark_results.json"))).summary;
const bench1 = JSON.parse(fs.readFileSync(R("reports/benchmark_results_run1_before_fixes.json"))).summary;
const load = JSON.parse(fs.readFileSync(R("reports/load_test.json")));
const e2e = JSON.parse(fs.readFileSync(R("reports/e2e_results.json")));
const csv = (p) => fs.readFileSync(R(p), "utf8").trim().split("\n").map((l) => l.match(/("([^"]|"")*"|[^,]*)(,|$)/g).filter((x, i, a) => i < a.length - 1 || x).map((c) => c.replace(/,$/, "").replace(/^"|"$/g, "")));

const FONT = "Times New Roman";
const W = 9026; // A4 text width in DXA with 1" margins
let fig = 0, tab = 0, eq = 0;
const body = [];
const para = (text, opt = {}) => new Paragraph({ alignment: opt.align || AlignmentType.JUSTIFIED, spacing: { after: 120, line: 300 },
  indent: opt.indent ? { firstLine: 0 } : undefined, keepNext: opt.keepNext, children: runs(text, opt) });
function runs(text, opt = {}) {
  // **bold** and _italic_ markup
  const out = [];
  const re = /(\*\*[^*]+\*\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size: opt.size || 24, bold: opt.bold, italics: opt.italics }));
    const t = m[0];
    out.push(new TextRun({ text: t.slice(t.startsWith("**") ? 2 : 1, t.startsWith("**") ? -2 : -1), font: FONT, size: opt.size || 24, bold: t.startsWith("**") || opt.bold, italics: t.startsWith("_") || opt.italics }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: opt.size || 24, bold: opt.bold, italics: opt.italics }));
  return out;
}
const P = (...texts) => texts.forEach((t) => body.push(para(t)));
const H1 = (t) => body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] }));
const H2 = (t) => body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] }));
const bullets = (items) => items.forEach((t) => body.push(new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 288 }, children: runs(t) })));
function equation(text) {
  eq += 1;
  body.push(new Paragraph({ tabStops: [{ type: TabStopType.CENTER, position: W / 2 }, { type: TabStopType.RIGHT, position: W }],
    spacing: { before: 120, after: 120 }, children: [new TextRun({ text: "\t", font: FONT }), ...runs(text, { italics: false }), new TextRun({ text: `\t(${eq})`, font: FONT, size: 24 })] }));
  return eq;
}
function pngSize(p) { const b = fs.readFileSync(p); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function figure(file, caption, widthIn = 6.2) {
  fig += 1;
  const s = pngSize(R(file));
  const wpx = widthIn * 96, hpx = (wpx * s.h) / s.w;
  body.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(R(file)), transformation: { width: Math.round(wpx), height: Math.round(hpx) },
      altText: { title: `Figure ${fig}`, description: caption, name: `fig${fig}` } })] }));
  body.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 200 }, children: [new TextRun({ text: `Figure ${fig}. `, bold: true, font: FONT, size: 20 }), ...runs(caption, { size: 20 })] }));
  return fig;
}
const border = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
function table(caption, header, rows, widths) {
  tab += 1;
  const total = widths.reduce((a, b) => a + b, 0);
  const ws = widths.map((w) => Math.floor((w / total) * W));
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0);
  body.push(new Paragraph({ keepNext: true, spacing: { before: 160, after: 60 }, children: [new TextRun({ text: `Table ${tab}. `, bold: true, font: FONT, size: 20 }), ...runs(caption, { size: 20 })] }));
  const cell = (t, i, head) => new TableCell({ width: { size: ws[i], type: WidthType.DXA }, borders: { top: border, bottom: border, left: border, right: border },
    shading: head ? { type: ShadingType.CLEAR, fill: "EDEDED", color: "auto" } : undefined, margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({ children: [new TextRun({ text: String(t), font: FONT, size: 18, bold: head })] })] });
  body.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: ws,
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }), ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false)) }))] }));
  body.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  return tab;
}
const pb = () => body.push(new Paragraph({ children: [new PageBreak()] }));

// ------------------------------------------------------------------ title page
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 240 }, children: [new TextRun({ text: "AeroFox", font: FONT, size: 56, bold: true })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: "An Evidence-Grounded Assistant for Spacecraft Fire Safety Built on NASA Microgravity Combustion Data", font: FONT, size: 32 })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Technical Report", font: FONT, size: 26, italics: true })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "NASA Space Apps Challenge 2026 — Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data", font: FONT, size: 22 })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1200 }, children: [new TextRun({ text: "AeroFox team · 15 November 2026 · Snapshot 2026-11-14.1 · Software version 1.1.0", font: FONT, size: 22 })] }));
body.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Abstract", font: FONT, size: 24, bold: true })] }));
P(`NASA has accumulated decades of combustion experiments in microgravity, but the results are spread across a repository of ${(66567).toLocaleString("en-US")} catalogued files, technical reports and heterogeneous tables, which makes them hard to use in design decisions. This report describes AeroFox, an assistant that answers natural-language questions about spacecraft fire safety from a verified, offline snapshot of the NASA Physical Sciences Informatics (PSI) combustion data. We first analysed the data: 24 investigations and 22 experiment tables were acquired with checksummed provenance, quality-audited and re-analysed. The analysis found that the PSI FLEX experiment table is mis-numbered for 119 of 274 tests relative to the official test list, that one Saffire-II sample was burned at about 25 cm/s rather than the tabulated 20 cm/s, and that a heptane droplet (FLEX-035) kept regressing at essentially its burning rate for about 25 s after its visible flame went out. No PSI solid-material flight test lies near the reduced-pressure, oxygen-enriched atmospheres proposed for lunar surface missions. These findings shaped the software: numbers come only from deterministic tools over corrected tables, every result carries its evidence status, and a locally controlled open-weight model plans tools and generates explanations. The deterministic evidence engine has independent tests and serves as the recovery path. See Section 16 for the separate runtime verification. `);
pb();
body.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Contents", font: FONT, size: 28, bold: true })] }));
// static contents list (LibreOffice does not compute Word TOC fields when exporting PDF)
["1. Introduction", "2. Scientific background", "3. Research questions and objectives", "4. Data sources", "5. Data acquisition and preprocessing",
 "6. Exploratory data analysis", "7. Scientific findings", "8. Language-model architecture selection", "9. Knowledge representation and retrieval",
 "10. Conversational reasoning and orchestration", "11. Scientific tools and numerical models", "12. Visualisation system", "13. Frontend and user experience",
 "14. Backend and deployment", "15. Reliability and security", "16. Testing and evaluation", "17. Results and demonstrable capabilities", "18. Discussion",
 "19. Limitations and future work", "20. Conclusions", "Acknowledgments and AI disclosure", "References", "Appendix A. Reproducibility"]
  .forEach((t) => body.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: t, font: FONT, size: 24 })] })));
pb();

// ------------------------------------------------------------------ 1
H1("1. Introduction");
P("Fire is one of the most severe hazards of crewed spaceflight. In a sealed vehicle there is nowhere to escape, the atmosphere is finite and must be recovered after a fire, and the physics of flames differs from what engineers know on Earth. Without gravity there is no buoyant convection: hot products do not rise, fresh oxidiser is not drawn in, and flames are fed only by ventilation flow and diffusion. Flame spread, extinction limits, smoke transport and detection all change.");
P("NASA has studied these effects on the International Space Station and in uncrewed resupply vehicles for more than fifteen years. The data are public in the Physical Sciences Informatics (PSI) repository, and the analyses are spread across NASA technical reports. The Flame in Freefall challenge asks for an interactive, AI-powered tool that summarises, ranks and interprets these findings and turns them into fire-safety insights for human exploration.");
P("AeroFox addresses this with three commitments: (i) the scientific evidence is acquired, audited and re-analysed before any software is designed; (ii) every number an answer shows is computed by deterministic, tested code from that evidence; and (iii) the assistant states what kind of evidence supports each claim and where the evidence ends. This report documents the data investigation (Sections 4–7), the resulting architecture (Sections 8–14), its verification (Sections 15–17) and its limits (Sections 18–20).");

H1("2. Scientific background");
H2("2.1 Combustion without buoyancy");
P("On Earth, the density difference between a flame and its surroundings induces flows of order 0.5–1 m/s that supply oxygen and remove products. In orbit this buoyant flow vanishes; flames become larger, cooler and more sensitive to radiative loss and to the forced flow imposed by ventilation. A thin solid that spreads a flame upward in 1 g may not burn at all in quiescent microgravity, while a material that self-extinguishes in a 1-g screening test may burn in the 'goldilocks' conditions of weak forced flow. Microgravity also simplifies flames into nearly one-dimensional geometries, which is why droplet and spherical flames are standard research configurations (NASA Researcher's Guide, 2015).");
H2("2.2 Droplet combustion and cool flames");
P("An isolated fuel droplet burning in a spherically symmetric flame follows, after a short transient, the d²-law (Eq. 1), in which the square of the droplet diameter decreases linearly with time at a rate given by the burning-rate constant K.");
equation("d²(t) = d₀² − K t");
P("K depends on fuel properties and on the ambient through the transfer number B (K ∝ ln(1 + B)), so it increases with ambient oxygen. In low oxygen, large droplets suffer radiative extinction because the flame stands far from the droplet and radiates more heat than it releases. For some hydrocarbons the hot flame is followed by a low-temperature 'cool flame' driven by peroxy chemistry at roughly 600–800 K, which is nearly invisible yet continues to consume fuel (Nayagam et al.; Dietrich et al., NASA/TP-2015-216046).");
H2("2.3 Spacecraft fire safety practice");
P("Spacecraft materials are screened with NASA-STD-6001 Test 1 (upward flame propagation in 1 g). Historically, ISS materials were qualified up to a maximum oxygen concentration of 30 % at sea-level pressure; Artemis surface missions consider 56.5 kPa total pressure with 34 % O₂, and an alternative of 66.2 kPa with 28.5 % O₂ (NTRS 20260002050). The Apollo 1 fire (100 % O₂ cabin), the Apollo 13 oxygen-tank failure and the 1997 Mir oxygen-generator fire are the incident record against which these choices are judged.");

H1("3. Research questions and objectives");
bullets([
  "RQ1. What combustion data does PSI hold, at what quality, and which of it can be reproduced from raw files?",
  "RQ2. Which quantitative findings relevant to fire safety can be defended from these data, and with what uncertainty?",
  "RQ3. Which engineering decisions (cabin materials, ventilation, detection, suppression, exploration atmospheres, lunar and Martian habitats) does the evidence support, and which does it not?",
  "RQ4. What architecture lets a conversational assistant answer new questions with these data without inventing numbers, and keep working when NASA's servers or the language-model provider are unavailable?",
]);
P("The engineering objective is a working, publicly deployable application whose outputs a reviewer can trace to NASA sources and reproduce.");

// ------------------------------------------------------------------ 4
H1("4. Data sources");
P("The primary source is NASA PSI, accessed through its JSON API: the repository search (research area 'combustion science'), the per-investigation metadata endpoint, the per-investigation file catalog and presigned download links. Secondary sources are 24 NASA Technical Reports Server (NTRS) records selected for specific claims (each record stores the reason it was included), and NASA web pages on the Apollo 1, Apollo 13 and Mir fires, the Researcher's Guide to Combustion Science and three NASA Spinoff articles. By team decision, complementary sources were restricted to NASA and agencies of U.S. allies; in this version no non-NASA dataset was ingested.");
table("Summary of the acquired evidence (snapshot 2026-11-14.1).", ["Source", "Content", "Count", "Redistributed"], [
  ["PSI investigations", "metadata, objectives, hardware, publications", "24", "yes (CC0-1.0 for 23)"],
  ["PSI experiment tables", "one or two per investigation", "22", "yes"],
  ["PSI file catalogs", "object keys and sizes", "66,567 entries", "yes (gzipped CSV)"],
  ["PSI raw files (curated)", "FLEX/CFI droplet histories and test sheets, FLEX-035 UV data, PSI-117 analysed CSVs, BASS matrices, DAFT, SAME-R results", "603", "yes"],
  ["PSI telemetry workbooks", "Saffire I, II, III", "3 (44 MB)", "no; derivatives only"],
  ["NTRS records", "metadata and abstracts; full text cached locally", "24", "metadata only"],
  ["NASA web pages", "incident and context statements", "8", "short quotations"],
], [2, 4, 1.3, 1.7]);
P("Every file is listed in a manifest with source URL, SHA-256, size, PSI object version and retrieval time. All 677 entries were verified in the run of 14 November 2026. Full NTRS texts are not redistributed because several records flag possible third-party material.");

H1("5. Data acquisition and preprocessing");
H2("5.1 Resilient acquisition");
P("PSI was intermittently unreliable in earlier work, so acquisition is isolated from the application. Each download uses separate connect and read timeouts, up to four retries with exponential backoff and full jitter on retryable statuses (408, 425, 429, 5xx) and connection errors, content-type validation, a size ceiling, a truncation check against Content-Length, SHA-256 checksums and atomic writes through a temporary file. A failed download never overwrites a verified file; the manifest then records the file as 'snapshot' (previously verified) rather than 'verified_this_run'. The application reads only the local snapshot and never contacts NASA when answering.");
H2("5.2 Processing");
P("A derivation step converts raw files into analysis tables, keeping raw values next to cleaned values and logging each transformation. Pressures are converted to kPa, oxygen is stored as a mole fraction and O₂ partial pressure is derived. The unit of analysis is stated for every table: one droplet test for FLEX and CFI, one burned sample for Saffire, one test point for BASS-II, one smoke-generation test for SAME-R.");
H2("5.3 Record linkage of the FLEX data");
P("The PSI FLEX table numbers its rows 1–274 in a column named 'FLEX Test #'. The per-test files (test sheets and droplet histories) are named by official FLEX number. Joining the two by number paired many tests with the wrong history. The NASA technical publication lists every test with its Combustion Integrated Rack (CIR) identifier; parsing it showed that test-sheet numbering agrees with the publication for 263 of 264 tests, whereas the PSI table agrees for only 153 of 272, with offsets of 1–6 after row 155 (tests omitted from the table). AeroFox therefore assigns the official FLEX number through the CIR identifier and joins all FLEX files on it.");
const qi = csv("outputs/tables/T03_quality_issues.csv");
table("Data-quality issues found and their handling (from the analysis notebook).", qi[0], qi.slice(1), [1.3, 3, 1.7, 3]);
figure("outputs/figures/fig02_missingness_heatmap.png", "Share of empty, 'none' or 'n/a' cells per column in the 22 raw PSI combustion tables. Source: PSI experiment tables. Unit: table column.", 6.0);

// ------------------------------------------------------------------ 6
H1("6. Exploratory data analysis");
H2("6.1 The archive");
P(`The 24 investigations reference ${(66567).toLocaleString("en-US")} files and 13.50 TB (13.47 TB after removing duplicate objects; 60,797 unique object keys). Figure 2 shows that ACME, CFI-G and FLEX imagery dominates the volume, while the analysis-ready material — tables, test sheets, droplet histories, telemetry and reduced aerosol data — fits in about 40 MB. This made a complete offline evidence snapshot feasible.`);
figure("outputs/figures/fig01_catalog_by_category.png", "PSI catalog entries per combustion investigation by file category (symmetric logarithmic axis). Source: PSI file catalog retrieved 14 Nov 2026. Unit: catalog entry.", 5.6);
H2("6.2 FLEX droplet tests");
const t4 = csv("outputs/tables/T04_flex_descriptive.csv");
const keep = ["fuel", "diluent", "n", "p_kPa_min", "p_kPa_max", "xO2_min", "xO2_max", "K_median", "K_q1", "K_q3", "K_cv"];
const idx = keep.map((k) => t4[0].indexOf(k));
table("Descriptive statistics of the FLEX tests by fuel and diluent (K in mm²/s; one test with 0 mmHg excluded).", ["fuel", "diluent", "n", "p min (kPa)", "p max", "X_O2 min", "X_O2 max", "K median", "K Q1", "K Q3", "CV"],
  t4.slice(1).map((r) => idx.map((i) => (isNaN(+r[i]) ? r[i] : (+r[i]).toFixed(+r[i] > 10 ? 1 : 3)))), [1.3, 1, 0.6, 1, 1, 0.9, 0.9, 1, 0.9, 0.9, 0.7]);
P("The FLEX test matrix is not factorial (Figure 3): CO₂ and helium dilution were explored mainly near one atmosphere, and the oxygen fraction was stepped down toward extinction. Pressure and diluent are therefore partly confounded and must be controlled for in any comparison.");
figure("outputs/figures/fig03_flex_condition_map.png", "Ambient conditions of FLEX tests by fuel and diluent; dashed lines are constant O₂ partial pressure. Source: PSI-69. Unit: droplet test.", 6.2);
figure("outputs/figures/fig04_flex_k_verification.png", "Burning-rate constant from the PSI table versus an independent fit of each raw droplet history. Left: joined through the CIR identifier; right: joined by the PSI table row number. Unit: droplet test.", 6.2);
P(`Refitting K from each raw droplet history (Eq. 1, ordinary least squares on 0.2–0.9 of the visible burn time) reproduces the tabulated values once the records are correctly linked: ${F.F02.result} The same comparison with the table's own numbering gives r = 0.729 (Figure 4), a concrete reproducibility hazard for any user of the PSI table.`);
equation("K = β₀ + β₁ X_O2 + β₂ ln(p / 1 atm) + β₃ [CO₂] + β₄ [He] + ε");
const t5 = csv("outputs/tables/T05_flex_K_regression.csv");
table("Regression of K (Eq. 2) by fuel; 95 % intervals from 2,000 bootstrap resamples of tests.", ["fuel", "term", "coefficient", "CI low", "CI high", "tests", "R²"], t5.slice(1), [1.2, 1.6, 1.1, 1, 1, 0.8, 0.8]);
P(`${F.F03.result} The increase with oxygen is consistent with d²-law theory; the higher K with helium dilution is consistent with helium's larger thermal diffusivity. The model is descriptive: tests were not randomised, droplet size is pooled, and the PSI table reports no measurement uncertainty for K.`);
figure("outputs/figures/fig05_flex_k_vs_o2.png", "FLEX burning-rate constant versus ambient O₂ mole fraction by diluent. Source: PSI-69 re-keyed. Unit: droplet test.", 6.2);
P(`Extinction behaviour follows the radiative-extinction picture: ${F.F11.result}`);

H2("6.3 Saffire, BASS-II and SAME-R");
P("The Saffire tables contain conditions and qualitative outcomes; spread rates are tabulated only for Saffire-II. BASS-II records calibrated O₂, CO₂ and CO before and after each test point in the Microgravity Science Glovebox, spanning about 15–22 vol % O₂ achieved by nitrogen dilution, but not the outcomes, which are in the NASA summary report. SAME-R provides per-test smoke particle moments for five materials and smoke-detector voltages.");
const t7 = csv("outputs/tables/T07_same_particle_size.csv");
table("Smoke particle arithmetic mean diameter (µm) by flight and material.", t7[0], t7.slice(1), [1, 1.2, 0.6, 1.3, 1, 1]);
figure("outputs/figures/fig10_same_particles.png", "SAME-R smoke particle arithmetic mean diameter by material (left) and versus aging time (right). Source: PSI-101 results workbook. Unit: smoke-generation test.", 6.2);

// ------------------------------------------------------------------ 7
H1("7. Scientific findings");
H2("7.1 Case A — Saffire-II ventilation");
const t6 = csv("outputs/tables/T06_saffire2_flow_comparison.csv");
const c6 = ["sample", "material", "flow_nominal_cm_s", "anem1_mean_cm_s", "anem2_mean_cm_s", "burn_time_s", "ug_spread_rate_mm_s"].map((k) => t6[0].indexOf(k));
table("Saffire-II: tabulated versus telemetry-measured duct flow (mean over 120 s after ignition).", ["sample", "material", "table (cm/s)", "anemometer 1", "anemometer 2", "burn time (s)", "spread (mm/s)"], t6.slice(1).map((r) => c6.map((i) => r[i] || "–")), [0.8, 2.2, 1, 1.1, 1.1, 1, 1]);
P(`${F.F05.result} The tabulated burn times agree with sample length divided by spread rate (29 cm ÷ 2.1 mm/s ≈ 138 s versus 145 s; 29 cm ÷ 2.6 mm/s ≈ 112 s versus 115 s), which supports the telemetry-based reading. With one sample per flow speed, the 24 % faster spread cannot be attributed to the 25 % higher flow with confidence, but any model validation must use 25 cm/s for sample 2-6. Sample 2-9 shows a 3 cm/s difference between anemometers, an estimate of local flow non-uniformity.`);
figure("outputs/figures/fig08_saffire2_flow.png", "Duct anemometer readings around ignition for Saffire-II samples 2-5 and 2-6. Source: PSI-99 telemetry. Unit: 1 Hz record.", 6.2);
P(`${F.F06.result}`);
H2("7.2 Case B — FLEX-035");
P(`${F.F04.result} Figure 8 shows the measured history: after the tabulated extinction time the regression continues on the same line for about 25 s and then stalls; the final samples, where the apparent diameter jumps, are an imaging artifact as the vapour cloud obscures the droplet and are excluded. What is measured here is the droplet regression; the cool flame itself is the interpretation of the FLEX science team. The engineering implication is that optical flame-out is not a reliable end-of-event signal for hydrocarbon liquid fires in microgravity.`);
figure("outputs/figures/fig07_flex035.png", "FLEX-035 (heptane, air, 102.4 kPa): measured d² with fits during visible burning and after visible extinction, and the UV camera signal. Source: PSI-69 raw files.", 6.2);
H2("7.3 Case C — detection");
P(`${F.F07.result} ${F.F08.result} The transferable conclusion concerns the particle population a detector must sense, not detector alarm performance.`);
H2("7.4 Case D — solid fuels and suppression");
P("BASS-II demonstrates that oxygen in a glovebox volume can be reduced by nitrogen dilution and predicted with a perfectly stirred reactor model calibrated against analyser readings (NASA TM 20210011385). The PSI table records the conditions of 129 test points, three of which report a final O₂ above the initial value by more than one percentage point; these are flagged as implausible. FLEX shows that helium dilution does not slow droplet burning relative to nitrogen at the same oxygen fraction (Table 4), which matters for the choice of inerting agent.");
H2("7.5 Case E — transfer to exploration systems");
P(`${F.F09.result}`);
figure("outputs/figures/fig12_conditions_vs_exploration_atmospheres.png", "Ambient pressure and O₂ fraction of individual PSI combustion tests versus proposed exploration atmospheres (stars). Unit: test.", 6.2);
P(`${F.F10.result} Lunar and Martian fire behaviour therefore cannot be obtained by interpolating between 1 g and orbital microgravity. Figure 10 codes which evidence supports which decision.`);
figure("outputs/figures/fig13_evidence_matrix.png", "Evidence coverage: direct (measured in the regime of the decision), partial (different regime, conditions only, or literature) or none.", 6.2);
H2("7.6 Consequences for the software");
bullets([
  "Analysis-ready evidence is small, so the application can carry it offline and never depend on PSI at answer time.",
  "Official tables contain linkage and labelling errors, so numbers must come from corrected tables at run time, with the discrepancy shown — not from a model's memory.",
  "Quantities differ in status (measured, derived, published, inferred), so every result carries an evidence type and locator.",
  "Several important questions (for example, a ranking of lunar fire risks) have no defensible numeric answer, so the tools return qualitative decision matrices with explicit ordering rules instead of invented scores.",
]);

// ------------------------------------------------------------------ 8
H1("8. Language-model architecture selection");
table("Architectures considered.", ["Option", "Strength", "Weakness for this problem", "Decision"], [
  ["General LLM alone", "fluent, flexible", "unverifiable numbers; no access to corrected tables", "rejected"],
  ["Vector RAG only", "grounding in text", "similarity ignores pressure, O₂, gravity; cannot compute", "rejected as sole method"],
  ["Fine-tuning / LoRA / QLoRA", "domain style", "no labelled reasoning data; corpus too small; memorises errors; needs GPUs", "rejected for this event"],
  ["Quantized independent LLM + scientific tools", "open weights and local inference", "latency and model loading depend on the host", "selected"],
  ["Commercial hosted inference", "remote infrastructure", "external dependency and variable inference cost", "replaced"],
], [1.8, 1.8, 3.2, 1.2]);
P("AeroFox 1.1 uses a team-controlled llama.cpp server with pinned quantized open weights. The Windows setup verifies the runtime and model file digests. The primary profile runs Qwen3-4B Q4_K_M on the RTX 3050 with Vulkan. The CPU profile uses Qwen2.5-1.5B-Instruct Q4_K_M. The model packages use Apache 2.0 terms. The model reads compact conversation and project context, proposes a short tool plan under a JSON grammar, and writes a response from the returned results. Numerical comparisons and figures remain calculations over the local snapshot.");

H1("9. Knowledge representation and retrieval");
P("The evidence store holds 90 items. These include 12 notebook findings, 30 curated NASA evidence entries with locators, 24 investigation records and 24 NTRS abstracts. The app also exposes 38 processed tables. Retrieval uses SQLite FTS5 with BM25 over titles, claims, quotations and topics, with English–Portuguese synonym expansion, and re-ranks results by an applicability score comparing each item's conditions with the scenario (Eq. 3), where each term is defined in SCIENTIFIC_METHODS.md.");
equation("score = BM25 × w_kind × (0.5 + mean(a_gravity, a_pressure, a_O2))");
P("Each result carries notes such as 'evidence from microgravity; scenario is lunar (not directly transferable)', which are shown to the user and passed to the model.");

H1("10. Conversational reasoning and orchestration");
P("Request interpretation preserves the current question and uses prior context where required. Explicit project terms and scientific identifiers constrain tool choices. The model can plan several registered tools. The server validates arguments and bounds requests, and supplies evidence and computation results for synthesis. It checks generated citations and screens for unsupported numbers. The app exposes evidence cards and figures from the tool outputs. An unavailable model or invalid generation invokes the offline evidence path with an explanation.");
P("The failure reported for earlier prototypes — a request for 'a chart about the main factor on fire safety … for a lunar base' producing no chart — was treated as an architectural requirement: the request is understood as a visualisation supporting a design decision, the fire-safety factor tool returns a decision matrix ordered by explicit rules (incident history, and whether the design condition lies outside tested conditions), and the answer states that it is not a calibrated risk ranking.");

H1("11. Scientific tools and numerical models");
table("Tool registry (selection). All tools validate inputs and return evidence identifiers and warnings.", ["Tool", "Computation", "Data"], [
  ["assess_atmosphere", "kPa conversion, pO₂, tests within ±10 kPa and ±0.03 X_O2, reference atmospheres", "FLEX, CFI, ACME, BASS-II, Saffire; NTRS 20260002050"],
  ["fire_safety_factors", "qualitative decision matrix with explicit tier rules", "fire_factors.json; findings; incident records"],
  ["chart_flex_burning_rate_vs_oxygen", "scatter and regression of K", "PSI-69"],
  ["flex035_case_study", "d² fits before and after flame-out", "PSI-69 raw"],
  ["saffire2_flow_case_study", "telemetry-measured flow per sample", "PSI-99"],
  ["smoke_particle_sizes", "AMD medians and IQR", "PSI-101"],
  ["materials_evidence", "per-material evidence table", "Saffire, BASS-II, SAME-R"],
  ["compare_gravity_regimes", "published LUCI rates; regime table", "NTRS 20250010653"],
  ["droplet_burn_time", "d²-law burnout", "user K or FLEX median"],
  ["simulate_ventilation", "compartment tracer model (Eq. 4)", "user or synthetic inputs"],
], [2.2, 3.4, 2.4]);
P("The compartment model treats each compartment i as well mixed with fixed volume V_i (Eq. 4), with inter-compartment flows Q_ij, clean supply S_i, exhaust E_i and a tracer source G_i(t); volume conservation (Eq. 5) is enforced and violating inputs are rejected.");
equation("V_i dC_i/dt = Σ_j Q_ji C_j − (Σ_j Q_ij + E_i) C_i + G_i(t)");
equation("S_i + Σ_j Q_ji = E_i + Σ_j Q_ij");
P("Integration uses the backward Euler method, which is unconditionally stable for this linear system and conserves tracer mass to round-off; RK4 is available for comparison. Verification: agreement with the analytic decay C₀ exp(−Qt/V) (maximum error below 5 × 10⁻³ with Δt = 1 s, below 10⁻⁶ with RK4), first-order convergence (error ratio ≈ 2 when Δt is halved), the steady state C = G/Q and a mass-balance error below 10⁻⁹ in the example network. The model has not been validated against fire measurements and does not represent flame spread, toxicity, detector alarm logic or suppression.");

H1("12. Visualisation system");
P("Tools return chart specifications (scatter, line, bar with error bars), tables and decision matrices; the browser renders them with Plotly or HTML tables. Because the written answer, the chart and the CSV export are all produced from the same tool output, the displayed numerical results remain traceable to the calculation. Every chart has a caption stating source and unit of analysis and a link to download the data behind it.");

H1("13. Frontend and user experience");
P("The interface preserves the team's existing visual identity: a navy sidebar with the AeroFox fox mark, a research library (NASA datasets, findings, references, field dictionary), the snapshot and engine status, and a white workspace with a large headline, four investigation cards and a composer offering project inputs and data filters (Figure 11). Answers show the engine used, the charts, evidence cards with status and quotation, a 'limits of this answer' box and a collapsible trace of tool calls. The layout works at 390 px width without horizontal scrolling, and all text is escaped before rendering.");
figure("docs/img/home.png", "AeroFox home page (desktop).", 6.2);
figure("docs/img/conversation.png", "An answer to the lunar-habitat question after the user supplied 8.2 psi and 34 % O₂: atmosphere coverage chart and comparison table (offline engine).", 6.2);

H1("14. Backend and deployment");
P("A single FastAPI process serves the frontend and uses a separate loopback inference process. Windows setup requires Python and downloads the pinned model and packages once. The team's host can publish the application temporarily through an HTTPS Cloudflare Quick Tunnel. The inference server remains private. The public configuration restricts concurrency and access to stored conversations. See DEPLOYMENT.md for reproduction and verification steps.");

H1("15. Reliability and security");
bullets([
  "Failures are explicit: tool errors are returned to the model as errors with an instruction not to substitute values; provider errors fall back to the offline engine with a notice; users never see stack traces, only a request identifier.",
  "Limits: 4,000-character messages, 64 kB bodies, per-client rate limit, daily budget of model-backed answers, bounded tool rounds and output tokens.",
  "Isolation: separate state and lock per session; artifacts downloadable only with their own session identifier.",
  "Injection resistance: retrieved text reaches the model only inside tool results and is declared as data; tools cannot run commands, write files or fetch URLs.",
  "Browser: strict Content-Security-Policy without inline scripts, no framing, escaped rendering. Secrets only from environment variables.",
]);

// ------------------------------------------------------------------ 16
H1("16. Testing and evaluation");
table("Offline baseline from the original archive (14 November 2026).", ["Suite", "Scope", "Result"], [
  ["pytest (52 tests)", "units, compartment verification, ingestion robustness, data integrity, retrieval, agent, historical mocked tool loop, API and security", "52 / 52 pass"],
  ["Benchmark single-turn", `40 topics × 3 styles = ${bench.single_turn.families} families`, `${bench.single_turn.passed} / ${bench.single_turn.cases} (first run ${bench1.single_turn.passed} / ${bench1.single_turn.cases})`],
  ["Benchmark multi-turn", `${bench.multi_turn.conversations} conversations, ${bench.multi_turn.turns} turns, state checked`, `${bench.multi_turn.passed} / ${bench.multi_turn.conversations}; ${bench.multi_turn.turns_passed} / ${bench.multi_turn.turns} turns`],
  ["Benchmark holdout", "30 questions not used for tuning", `${bench1.holdout.passed} / 30 first run; ${bench.holdout.passed} / 30 current`],
  ["Browser end-to-end", "Playwright, desktop and mobile", `${e2e.results.filter((r) => r.ok).length} / ${e2e.results.length}`],
  ["Load", `${load.users} users × ${load.turns_per_user} turns`, `${load.errors.length} errors; ${load.isolation_ok}/${load.users} isolated; p95 ${load.latency_s.p95} s`],
], [1.8, 4.2, 2]);
P("A benchmark case passes when an expected tool runs successfully, every expected chart, table or matrix is returned with data, no tool fails and the answer is non-empty. Grading is automated; the benchmark therefore measures tool choice and rendered outputs, not the quality of prose. Between the first and current runs, general understanding rules were improved from single-turn failures (full experiment names, 'percent', plural 'fans', accent-insensitive Portuguese aliases, gravity comparisons) and one expectation was corrected. The remaining holdout failures are reported rather than tuned away. The brief targeted about 300 single-turn cases; 243 were built.");
P("The historical benchmark in this table predates independent inference. The migrated Qwen3-4B profile passed seven of seven API turns on a Windows RTX 3050 laptop GPU. Median response time was 6.47 s, with a range of 5.33 to 9.83 s. The CPU Qwen2.5-1.5B profile passed the same seven cases before the final evidence additions, with median 16.97 s. The migrated unit, integration and data suite passed 53 tests. The new notebook run completed all 26 code cells in local Jupyter. Desktop and mobile Chromium rendered real inference output, and a signed-out browser also rendered the measured Saffire chart through a temporary HTTPS tunnel. The benchmark checks grounding structure and artifacts. It does not establish scientific correctness of every generated claim.");

H1("17. Results and demonstrable capabilities");
P("Representative end-to-end interactions verified in the browser:");
bullets([
  "'Do a chart about the main factor on fire safety I should consider while projecting a lunar base.' → decision matrix of ten factors with atmosphere, ignition sources, oxygen systems, materials and egress as Tier 1, the incident and coverage basis of each, and the statement that it is not a risk score.",
  "'We plan 8.2 psi and 34 % oxygen. Now change the atmosphere and compare the results.' → 56.54 kPa and 19.22 kPa O₂ partial pressure, the coverage chart showing no nearby solid-material tests, and an updated matrix, with project state preserved.",
  "'Compare Saffire-II runs 2-5 and 2-6' → measured flows of 20.0 and 25.0 cm/s against the tabulated 20 cm/s, with chart, table and CSV export.",
  "'O que acontece se a ventilação falhar?' → answer in Portuguese with a synthetic compartment simulation, clearly labelled.",
  "'Which findings are based on actual measurements?' → the evidence of the previous answer classified as measured, published or incident record.",
]);

H1("18. Discussion");
P("The most useful results of the project came from treating NASA's tables as data to be verified rather than as ground truth. Two of the strongest findings — the FLEX numbering drift and the Saffire-II flow discrepancy — are record-keeping problems that would silently corrupt any analysis or AI system consuming the tables directly. The FLEX-035 analysis shows how raw time series add physical insight beyond summary tables. The coverage analysis answers a question engineers actually face: whether the microgravity evidence base supports the atmospheres planned for lunar surface missions. It does not, for solid materials.");
P("The architecture reflects these lessons. The language model contributes understanding and explanation, while calculations, charts and evidence status are fixed by code. This makes the system auditable but limits its scope to what the tools can compute; questions outside the tools receive retrieved evidence and an explicit statement of the gap. The offline engine is robust but its prose is templated. Small-model prose and retrieval require review on unfamiliar conditions.");

H1("19. Limitations and future work");
bullets([
  "The judged public endpoint and long-duration operation require a separate acceptance run.",
  "Data not included: NASA-STD-6001 test databases, battery thermal-runaway data, SoFIE and FM² results, video and imagery, non-NASA datasets (JAXA, ESA, NIST).",
  "Models: the compartment model is a passive tracer; no fire-growth, toxicity or detector model is implemented. Regressions are descriptive.",
  "Evaluation: automated benchmark of tool choice and outputs; no expert grading of answer quality; paraphrases written by the developers.",
  "Future work: expert review panel, extraction of BASS-II outcomes from the NASA TM, partial-gravity data as FM² publishes, larger model comparison, persistent sessions.",
]);

H1("20. Conclusions");
P("A complete, checksummed offline snapshot of the analysis-ready NASA PSI combustion data was built and re-analysed. The analysis corrected record-linkage errors in official tables, reproduced published burning-rate constants from raw data, showed continued droplet regression after visible flame-out, reconstructed the actual ventilation of a Saffire-II test, and established that PSI solid-material flight data do not cover the reduced-pressure, oxygen-enriched atmospheres planned for lunar surface missions. AeroFox makes these results usable through a conversational interface whose numbers and charts come only from tested tools, whose evidence is labelled by status, and which continues to work without NASA's servers or a language-model provider. Its recommendations are preliminary engineering analysis and are presented as such.");

H1("Acknowledgments and AI disclosure");
P("Data courtesy of NASA Physical Sciences Informatics and the NASA Technical Reports Server. AeroFox is an independent team project. Claude Code assisted the earlier implementation. OpenAI Codex assisted the independent inference migration, checks and documentation. The runtime uses locally controlled open weights. Scientific values and figures derive from validated Python tools.");

H1("References");
const refs = [
  "Dietrich, D.L., Ferkul, P.V., Bryg, V.M., Nayagam, M.V., Hicks, M.C., Williams, F.A., Dryer, F.L., Shaw, B.D., Choi, M.Y., Avedisian, C.T. (2015). Detailed Results from the Flame Extinguishment Experiment (FLEX) March 2009 to December 2011. NASA/TP-2015-216046. NTRS 20150023456.",
  "Ferkul, P., Olson, S., Urban, D.L., Ruff, G.A., et al. (2017). Results of Large-Scale Spacecraft Flammability Tests. 47th International Conference on Environmental Systems. NTRS 20170008805.",
  "Ruff, G.A., Urban, D.L. (2016). Operation and Development Status of the Spacecraft Fire Experiments (Saffire). ICES 2016. NTRS 20170000230.",
  "Olson, S.L., Ferkul, P.V., Bhattacharjee, S., Miller, F.J., et al. (2021). Burning and Suppression of Solids–II (BASS-II) Summary Report. NASA TM. NTRS 20210011385.",
  "Urban, D.L., Ruff, G.A., Greenberg, P.S., Fischer, D., et al. (2012). Particle Morphology and Size Results from the Smoke Aerosol Measurement Experiment-2. ICES 2012. NTRS 20130000422.",
  "Ferkul, P.V., Johnston, M.C., Kralik, N., Liao, Y.-T. (2025). Lunar Combustion Investigation: Flammability Results from a Rotating Sounding Rocket. NTRS 20250010653.",
  "Zayac, J., Johnston, M., Ruff, G., Ferkul, P. (2024). Flammability of Materials on the Moon. NTRS 20240008623.",
  "Alpert, B.K., Kennedy, L., Welsh, L.D., Young, A. (2026). Surface Vehicle Atmospheric Considerations for Moon to Mars Exploration. ICES 2026. NTRS 20260002050.",
  "Ferkul, P., Brown, L., Mroczka, C., Bhattacharjee, S. (2019). Solid Fuel Ignition and Extinction (SoFIE) Project on ISS. NTRS 20200000361.",
  "Nayagam, V., Dietrich, D.L., Hicks, M.C., Williams, F.A. (2014). Cool-flame Extinction During N-Alkane Droplet Combustion in Microgravity. NTRS 20140006750.",
  "Gokoglu, S.A., Dietrich, D.L., Stocker, D.P., Ferkul, P.V., Olson, S.L., Hicks, M.C. (2015). A Researcher's Guide to: Combustion Science. NASA ISS Research Integration Office.",
  "NASA Office of Safety and Mission Assurance. Apollo 1 (AS-204) and Apollo 13 — Agency Close Calls & Lessons Learned. https://sma.nasa.gov/sma-disciplines/accllp/",
  "Uri, J. (2022). 25 Years Ago: Fire Aboard Space Station Mir. NASA.",
  "NASA Physical Sciences Informatics. Combustion science investigations PSI-10, -20, -21, -22, -23, -25, -26, -39, -47, -60, -62, -68, -69, -98, -99, -100, -101, -102, -106, -107, -115, -117, -142, -159. https://psi.nasa.gov/physci/repo (accessed 14 Nov 2026).",
  "NASA (2016 and revisions). NASA-STD-6001, Flammability, Offgassing, and Compatibility Requirements and Test Procedures (context only; not ingested).",
];
refs.forEach((r, i) => body.push(new Paragraph({ spacing: { after: 80 }, indent: { left: 540, hanging: 540 }, children: [new TextRun({ text: `[${i + 1}]\t${r}`, font: FONT, size: 20 })] })));

H1("Appendix A. Reproducibility");
bullets([
  "Repository layout: backend/ (code), frontend/, data/ (raw, processed, curated, findings), notebooks/, tests/, scripts/, docs/, reports/.",
  "Data refresh: python -m aerofox.ingest.psi_snapshot; python -m aerofox.ingest.derive (from backend/).",
  "Notebook: notebooks/AeroFox_Comprehensive_Data_Analysis.ipynb, runs in Colab on CPU in about one minute; regenerates outputs/ and data/findings/findings.json.",
  "Tests: python -m pytest -q; python tests/benchmark/run_benchmark.py; node tests/e2e/e2e.js; python scripts/load_test.py.",
  "Run: START_AEROFOX.bat on Windows. See docs/MODEL_RUNTIME.md for other environments and the selected weights.",
  "Main artefacts: docs/AeroFox_Technical_Report.pdf, reports/benchmark_results.json, reports/load_test.json, reports/e2e_results.json, data/raw/psi/manifest.json.",
]);

const doc = new Document({
  creator: "AeroFox team", title: "AeroFox Technical Report", description: "NASA Space Apps 2026 Flame in Freefall",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24, color: "000000" } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true, color: "000000" }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 24, bold: true, italics: true, color: "000000" }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    children: body,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(R("docs/AeroFox_Technical_Report.docx"), buf); console.log(`wrote report: ${fig} figures, ${tab} tables, ${eq} equations`); });
