# Testing and evaluation

The sections below the migration checks describe the original 1.0.0 offline baseline.

## Run the independent-model checks

Start the Windows launcher and confirm the local model is ready at /api/health. Run python tests/benchmark/live_open_model.py --url http://127.0.0.1:8000 --output reports/model-run.json. The benchmark requires a real model, successful scientific tool, usable figures, citation IDs and state where specified. Review the returned prose separately from the automated score. Run python -m pytest -q for deterministic and mocked-protocol regression coverage.

Model-enabled tests must not be combined with an offline suite or another process using the same inference slot.

## Historical offline baseline

All numbers below were produced on 14 Nov 2026 in the development container (Linux, Python 3.13) and are stored in
`reports/`. "Offline engine" means no language model was available; **no live Claude call was made** during development.

## How to run

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest -q
```

```bash
python tests/benchmark/run_benchmark.py
```

```bash
node tests/e2e/e2e.js http://127.0.0.1:8000
```

```bash
python scripts/load_test.py --users 50 --turns 4
```

(The E2E and load tests need a running server; start the load-test server with a high `AEROFOX_RATE_PER_MINUTE`.)

## Results

| Suite | What it covers | Result |
|---|---|---|
| `tests/test_science.py` | unit conversions, O₂ %/fraction, analytic and convergence verification of the compartment model, mass balance, invalid-model rejection, d²-law, atmosphere warnings | pass |
| `tests/test_data_integrity.py` | manifest checksums (600+ files), catalog counts, FLEX re-keying (r > 0.98), FLEX-035 values, Saffire-II 2-6 flow, physical ranges, findings completeness | pass |
| `tests/test_ingest.py` | retry with backoff on 5xx, last-known-good preserved on failure, content-type/status validation, size limit, unreachable host | pass |
| `tests/test_agent.py` | intent/entity extraction EN/PT, critical lunar-chart request, 5-turn continuity, 8 concurrent sessions isolation, hostile input, retrieval recall, **mocked Claude loop**: tool charts attached, fake citation removed, tool error passed as error, provider outage → offline, refusal → offline, budget → offline | pass |
| `tests/test_api.py` | response contract, CSV export, cross-session artifact access denied, input validation, path traversal, security headers, rate limiting | pass |
| **Total** | | **52 / 52** |

### Scenario benchmark (`tests/benchmark/`, offline engine)

A case passes when an expected tool ran successfully, every expected block type (chart/table/matrix) was returned with data,
no tool failed and the answer is non-empty. Automated; no human grading.

| Set | Size | First run | Current |
|---|---|---|---|
| Single-turn: 40 topics × 3 styles (plain EN, paraphrased/technical EN, PT) = 120 families | 243 cases | 224 / 243 | 243 / 243 |
| Multi-turn conversations (5 systems × 3 atmospheres × 3 follow-up sequences; state retention checked each turn) | 45 conv. / 180 turns | 45 / 45 | 45 / 45 |
| Holdout (written separately, not used to tune the engine) | 30 | **26 / 30** | 27 / 30 |
| Latency (offline) | | p50 2 ms, p95 10 ms | |

Between the first and current run, general fixes were made from single-turn failures (full experiment names, "34 percent",
plural "fans", accent-folded Portuguese aliases, gravity comparisons without the word "compare"); one expectation was
corrected (exporting in a fresh session should report that nothing exists to export). The holdout improvement (Mars vs Moon)
came from the general gravity rule, not from tuning on the holdout. Remaining holdout failures (reported, not fixed):
"wall panels for a lunar lander at 34 % O₂" (got the coverage matrix instead of a design review), "the heptane droplet that
kept vaporizing" (got the FLEX K chart instead of FLEX-035), "Is the ISS cabin atmosphere covered by solid-material tests?"
(got a factor matrix instead of an atmosphere assessment).

Targets in the brief were ~300 single-turn cases and 30 holdout cases; actual: 243 and 30.

Limits of this benchmark: it checks tool choice and rendered outputs, not the scientific quality of prose; the paraphrases
were written by the developers; the LLM path is evaluated only with a mocked provider.

### Browser end-to-end (`tests/e2e/e2e.js`, Playwright/Chromium)

25 / 25 checks: home page, cards, counts, chart rendering (Plotly `data-rendered`), decision matrix for the critical
lunar-base chart request, atmosphere follow-up chart, CSV download, evidence drawer, project inputs save, Portuguese
simplification, five library views, new/restore conversation, mobile (390 px) without horizontal overflow, zero console
errors. One real bug was found and fixed this way (number input `step` blocked saving 56.54 kPa).

### Load (`reports/load_test.json`)

50 concurrent users × 4 turns: 200 requests in 0.75 s, 0 errors, 50/50 sessions kept their own O₂ value,
p50 0.093 s, p95 0.50 s, max 0.54 s (offline engine, single process).

### Clean-environment reproducibility

The release ZIP was extracted into an empty directory and a fresh virtual environment was created from
`requirements-dev.txt`: 52/52 tests passed and the notebook executed 26/26 code cells with 0 errors, regenerating
`findings.json` identically. This check found one missing dependency (SciPy, needed for Spearman correlations), now added.
The launcher was verified from a clean `.venv` (runtime requirements only).

### Not tested

Live Claude responses and their latency/cost; Windows execution of `START_AEROFOX.bat` (launcher logic tested on Linux);
Docker image build (no Docker daemon available; the image's file set was assembled and smoke-tested); a deployed URL.

## Verified results for 1.1.0

| Check | Result |
| --- | --- |
| Windows launcher and inference startup | Auto selected Qwen3-4B on the 6 GB RTX 3050, started the cached pinned Vulkan executable and opened the app on port 8000. |
| GPU model HTTP | Seven of seven turns using real inference. Median 6.47 s, range 5.33–9.83 s. See reports/independent_model_gpu.json. |
| CPU model HTTP | Seven of seven turns using real inference on the same prompts before the final evidence additions. Median 16.97 s. See reports/independent_model_cpu.json. |
| Unit, integration, ingestion, and science | 53 tests passed on Windows. |
| Offline benchmark after migration | 243 of 243 single-turn cases, 45 of 45 conversations and 27 of 30 holdout questions. See reports/offline_after_migration.json. |
| Local browser | The exact lunar-base question and Mars follow-up both rendered populated matrices from real inference. Chromium checked verified results, export CSV, a measured plot at 390 px and browser exceptions. Run node tests/e2e/independent_model.cjs. |
| Temporary judge URL | A signed-out 390 px Chromium session loaded the app over HTTPS through an actual Quick Tunnel, generated a Saffire answer, rendered its measured chart and exposed its CSV link. The test tunnel was closed. See reports/public_demo.json. |
| Notebook | All 26 code cells executed in a fresh local Jupyter kernel. The Colab ZIP-upload branch was revised and reviewed. Remote Colab was not used. |

Real-inference pass assertions cover mode, model token counts, required tool, populated visual blocks, at least one available citation and scenario state where specified. The run is a small task sample. Scientific tools return independent values and warnings. Generated qualitative statements need editorial review for causal wording, overly broad conclusions and incomplete project assumptions. Report reproduced versus potential failures explicitly. This release does not establish unrestricted correctness of a generative model.

## Version 1.1.1 verification

- Run `python -m pytest -q` for the deterministic API, export, grounding and recovery tests.
- Run `python tests/benchmark/live_open_model.py --url http://127.0.0.1:8001 --output reports/reliability_111_live.json` against a matching local model service.
- Run `node tests/e2e/independent_model.cjs http://127.0.0.1:8001` with Playwright Chromium for the Moon-to-Mars visual, measured chart, mobile workflow and exported Mermaid.
- See [reliability and security audit](AUDITORIA_1.1.1.md) and [visual formats](VISUALIZATIONS.md).
