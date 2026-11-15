# Imported baseline audit

This preserves the 1.0.0 findings for provenance. The current independent runtime and revised evidence are in MODEL_RUNTIME.md and ../CODEX_HANDOFF.md.


## 1. Baseline audit (14 Nov 2026, 22:02 UTC)

| Item | Finding | Impact | Action |
|---|---|---|---|
| Workspace | `/home/user` was empty: no repository, no prototype ZIP, no PDFs, no `FLEX_Cruzamento_Fichas_e_Tabela.csv`, no notebooks, no previous frontend/backend | Nothing to preserve, test or reproduce; earlier failures (crashes, missed charts) could not be reproduced | Rebuilt from scratch; treated earlier failure reports as requirements |
| GitHub | No GitHub account linked to the session | Cannot inspect or push an existing repo | Local git repo with commits; push commands in START_HERE |
| Visual reference | Home-page screenshot and logo provided mid-session | Defines identity | Reproduced layout; logo redrawn as SVG |
| Network | NASA hosts blocked by default policy | Data phase blocked | Allow-listed psi/ntrs/nasa/science/standards/sma/spinoff hosts (with user approval) |
| LLM | No Anthropic API key in the environment | Live model untestable | Offline engine + mocked-provider tests; key configurable via `.env` |
| Docker | CLI present, no daemon | Image not buildable here | File set simulated and smoke-tested |
| Competition site | TLS chain fails via proxy; WebFetch blocked | Rules not verified | Requirements taken from the brief; marked "verify" |

Inherited-audit numbers were verified (see DATA_SOURCES.md): 24 investigations, 22 tables, 66,567 catalog entries confirmed;
deduplicated count 60,797 vs 60,866 reported; 13.47 TB corresponds to the deduplicated volume.

Scientifically questionable assumptions found in NASA's own tables: FLEX test numbering drift; FLEX burning-rate column
labelled "mm"; one FLEX test at 0 mmHg; Saffire-II 2-6 flow 20 vs 25 cm/s; Saffire-II O₂ derived from CO₂; Saffire-I
length/width transposed; BASS-II final O₂ above initial; "037 mm" thickness; zero particle moments meaning "not measured".

## 2. Requirements → implementation matrix

| Requirement | Component | Verification | Result | Status | Remaining limitation |
|---|---|---|---|---|---|
| Resilient NASA acquisition (retry, backoff, validation, checksums, last-known-good) | `ingest/fetch.py`, `psi_snapshot.py` | `test_ingest.py`; 2 live runs | 677/677 verified | passed | Not scheduled; manual refresh |
| Offline, versioned snapshot | `data/`, manifest | checksum test | 600+ files OK | passed | Telemetry workbooks cache-only |
| Colab analysis notebook with outputs | `notebooks/…ipynb` | executed end-to-end (nbconvert) | 13 figures, 10 tables, 12 findings | passed | Colab run itself not performed here |
| Findings catalog feeding the agent | `data/findings/findings.json` | completeness test | 12 findings | passed | |
| Hybrid retrieval with applicability | `evidence/store.py` | recall test | ≥ 7/8 targets in top-5 | passed | No embeddings (not needed at this corpus size) |
| Tool-using agent, no invented numbers | `agent/tools.py`, `llm.py` | mocked-provider tests | pass | partial | **Live Claude untested** |
| Offline fallback | `agent/planner.py` | benchmark | 243/243, 45/45 | passed | Template prose; EN summaries in PT answers |
| Context and typed project memory | `agent/state.py` | multi-turn benchmark, tests | 180/180 turns | passed | In-memory only |
| EN + PT | `nlu.py`, planner | PT benchmark | 81/81 | passed | |
| Charts rendered from canonical data | frontend + blocks | E2E (`data-rendered`) | 25/25 | passed | |
| Critical "chart about main lunar fire factor" | `fire_safety_factors` | test + E2E | matrix rendered | passed | Qualitative by design |
| Compartment simulation, verified | `science/compartment.py` | analytic, convergence, mass balance | pass | passed | Not validated against fire data |
| CSV export behind charts | API | API + E2E | pass | passed | |
| Session isolation, concurrency | `SessionStore` | 8-thread test, 50-user load | 50/50 | passed | Single process |
| Security controls | API middleware | API tests | pass | passed | `pip-audit` not run |
| Local Windows launcher | `START_AEROFOX.bat`, `launch.py` | clean-venv run on Linux | pass | partial | Not executed on Windows |
| Public deployment | Dockerfile, render.yaml | image file-set smoke test | pass | not run | Needs team account |
| GitHub publication | git repo | 6 commits | — | not run | Needs team credentials |
| Technical report DOCX + PDF | `docs/AeroFox_Technical_Report.*` | rendered and inspected | — | see report | |

## 3. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NASA PSI unavailable during demo | medium | none at runtime | offline snapshot; refresh isolated |
| API key missing/invalid/rate-limited | medium | lower answer fluency | automatic offline fallback with notice |
| Runaway model cost on public URL | medium | money | daily turn cap, rate limit, effort medium, console spend limit |
| Free host asleep when judges open it | high | 1-min first load | wake before judging; note in submission |
| Judges ask outside the evidence | high | weak answer | explicit "no evidence" + evidence search; never fabricated |
| Misreading qualitative matrix as risk score | medium | credibility | caption and text state it is not a calibrated ranking |
| Lunar/Mars over-extrapolation | medium | scientific error | gravity guardrails in prompts, tools and warnings |
| Session loss on restart | low | user annoyance | clear "expired" message |

## 4. Execution log (UTC, 14 Nov 2026)

22:02 empty workspace audited · 22:05 NASA hosts allow-listed · 22:07 first PSI snapshot (47 files) · 22:12 full snapshot
(677 files) · 22:20 NTRS references (24) · 22:25 Saffire-II telemetry reconstruction · 22:30 FLEX re-keying via NASA/TP ·
22:40 notebook executed (13 figures, 12 findings) · 22:50 backend, agent, tools · 22:55 frontend · 23:00 tests (52) ·
23:03 benchmark run 1 (224/243, holdout 26/30) → fixes → 243/243, 27/30 · 23:05 E2E 25/25 after one fix · 23:06 load test ·
23:08 launcher verified from clean venv · docs and report.
