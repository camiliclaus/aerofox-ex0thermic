# AeroFox continuation and acceptance record

## A. Objective

AeroFox is a scientific conversational assistant for NASA Space Apps Challenge 2026, Flame in Freefall. Default operation uses an open-weight model on team-controlled hardware. Protect scientific provenance, reproducibility, the established UI and the original NASA analysis.

## B. Source and checkpoints

The independent migration started from AeroFox_release.zip, SHA-256 3258a4bfb0ff5a82246b75d7a53f84c94e9c7e133409d543b03b502110a6ad97. The original Git import was 7b5727f150c81b1c3327923a42a38686697d41e7 and the migration checkpoint was 7c5cd9570a1491d641f1e0a500784ba08730976a. A team repository initialized from this ZIP has its own history.

## C. Completed implementation

Release 1.1.0 has a loopback llama.cpp agent producing real generated prose after a grammar-constrained plan and Python tools. Default Windows selection uses Qwen3-4B on an eligible NVIDIA card and Qwen2.5-1.5B on CPU-only hosts. Claude SDK, provider, default runtime configuration and legacy Render blueprint were replaced. The model cannot make project edits, start commands or provide URLs to tools. Existing scientific controls, citation cards, Plotly UI and CSV export remain. Figures derive from validated results. Model prose excludes unverified numerical sentences, and deterministic values appear under Verified results. The UI distinguishes actual runtime and offline recovery.

## D. Status and partial work

The API and several browser paths ran with the real model. Early integration failures included bad tool choice, Mars state loss for a verbal outpost description, missing source IDs and unsupported prose quantities. The migration adds normalized scope resolution, bounded plans, scientific render contracts and conservative generation validation. Report automation is scripts/build_report.js and Word PDF export. The 26-cell notebook executed in a fresh local kernel. Remote Google Colab execution remains to be tested. See reports for the most recent real inference output and check this file against the release hash.

## E. Requirements still open

A long-duration judged session, real traffic beyond the demonstration budget, independent aerospace review, a larger bilingual quality evaluation and an 8B/Gemma benchmark were outside the verified set. A stable public URL needs an available team host or a team-controlled named tunnel. Model tuning and semantic embeddings were not required to prove independence. The app still relies on a compact evidence index and narrow numerical solvers. Unsupported scientific claims can slip through generated prose even though unverified numbers are withheld.

## F. Decisions

Use llama.cpp b8230 because the project can pin both CPU and Vulkan artifacts, explicitly constrain planner JSON, and keep the inference port private. Two model generations normally occur, a plan and grounded qualitative synthesis, with one bounded repair if required. Deterministic exact accessions, explicit engineering scopes and chart requests guard the corresponding tool. Existing FTS lexical retrieval and applicability checks preserve scientific scope. Keep measured, reported, synthetic and simulated results distinct.

## G. Evidence and data

Snapshot 2026-11-14.1 covers 24 investigation records, 22 experiment tables and 38 processed tables. Keep NASA PSI manifest, raw provenance and scientific derivations together. FLEX identification uses the CIR identifier, FLEX-035 distinguishes post-extinction measured regression from the published cool-flame interpretation, and Saffire-II distinguishes tabulated and calibrated flow. EVA wire-break and exterior Moon/Mars reference cards add scoped evidence from primary NASA sources. See docs/DATA_SOURCES.md and docs/SCIENTIFIC_METHODS.md. The passive tracer models a given transport network under its assumptions.

## H. Models and hardware

Windows host has an NVIDIA RTX 3050 6GB Laptop GPU. Tested Qwen3-4B Q4_K_M Vulkan configuration uses one 8192-token slot and disables extended reasoning. The roughly 2.50 GB weights and pinned GPU artifact are published and their SHA-256 values live in scripts/local_model.py. CPU profile uses Qwen2.5-Instruct 1.5B Q4_K_M. Both model weights use Apache-2.0 terms. Weights and executable ZIPs are cached under .models on the delivered machine and omitted from the portable release. See docs/MODEL_RUNTIME.md.

## I. Verification

Run python -m pytest -q with requirements-dev.txt installed. Windows FastAPI tests require loopback socket access. Run python tests/benchmark/live_open_model.py --url http://127.0.0.1:8000 --output reports/model-run.json for measured real inference. Inspect the required artifacts and prose in reports/independent_model_gpu.json. Compare equivalent CPU and GPU outputs using the same snapshot and branch. Rerun the browser for desktop and mobile, CSV and citation controls. The scientific data itself is unchanged apart from the additional literature cards. The current Windows launch and real model checks are recorded in docs/TESTING.md.

## J. Deployment

Windows: START_AEROFOX.bat. Use --model-profile cpu on Windows hosts with limited GPU support or --offline for deliberate testing. Use scripts/launch.py --external-local-model where model supervision is supplied by the operator. Local URLs and inference endpoints are distinct. A signed-out Chromium test passed over an actual temporary Cloudflare Quick Tunnel with a real model response, visible plot and CSV link. The tunnel was closed at the end of the test. Use docs/DEPLOYMENT.md and scripts/share_demo.ps1 to start another for judging. The originating app must stay open. GitHub distribution uses the source ZIP and its checksum. Teammates can use the local Git repo or import the archive under a team-owned remote.

## K. Known limitations and defects

The CPU profile is slower and may require offline recovery on some scientific prompts. Current source validation checks the admissibility of citation IDs, quantitative provenance and structural tool output. Independent claim-by-claim human scientific review remains necessary for broader questions. Some secondary tools selected by the model may be related without being necessary. Explicitly unsupported design questions should return qualitative evidence and conditions. The Quick Tunnel endpoint is ephemeral. Browser cancel discards stale client updates while the bounded server-side turn can finish.

## L. Exact continuation

1. Confirm git status and preserve the most recent tested archive.
2. Reproduce the Windows startup and query API health, then verify model state and output through the browser using docs/TESTING.md.
3. Expand the bilingual evaluation, including unseen physical boundary conditions and multi-turn corrections. Evaluate experimental higher-capacity models with the same tools and data. Keep held-out cases outside prompts.
4. Review qualitative answers against primary sources and improve narrow retrieval, source relevance and unsupported claims. Preserve exact numbers in validated tools.
5. Reopen the public workflow on the intended host, verify the HTTPS URL from a signed-out browser and complete team submission when authorized. Regenerate the DOCX and PDF and archive with checksum after substantive changes.

## M. Files

Code is under backend/aerofox and frontend. Science is under backend/aerofox/science and data. Notebook and reports are under notebooks and docs. Use scripts/package_release.py to rebuild the ZIP. See TEAM_GUIDE.md for maintained edit locations. PROMPT_FOR_CODEX.md in this folder provides standalone continuation instructions.

## N. Acceptance

Default local launch loads a real independent model without commercial keys. The actual browser can answer unseen English and Portuguese scientific questions with evidence, maintain named scenarios, select valid tools and show sourced charts and downloads. Data audit and tests are reproducible from the bundle. Operational failures are bounded and visible. The team can recreate a free public link without exposing inference. Every reported pass maps to executed checks and known limitations remain explicit.


### Delivery verification

The final GPU benchmark passed 7/7 real model turns (median 6.47 s). The CPU benchmark passed the same seven prompts on the pre-final evidence revision (median 16.97 s). Fifty-three Windows tests passed. The offline benchmark passed 243/243 single turns and 45/45 conversations, with 27/30 on its historical holdout. The local Chromium checks verified the exact lunar base prompt, the Mars continuation, a measured chart at 390 px and actual CSV. The signed-out HTTPS test for the Saffire chart passed before the tunnel was closed. The notebook ran all 26 cells locally.

## Follow-up maintenance, version 1.1.1

Version 1.1.1 was developed from the verified 1.1.0 release ZIP and tested with the loopback Qwen3 service on port 8796. The launcher prints the actual app address at startup.

Read docs/AUDITORIA_1.1.1.md for the observed inference failure, the safeguards and the reproduction results. Read docs/VISUALIZATIONS.md for the Python workflow tool, in-app chart and Mermaid export. Regression files are tests/test_agent.py, tests/test_api.py, tests/e2e/independent_model.cjs and reports/reliability_111_live.json. The scientific report PDFs in this checkout describe the 1.1.0 migration. The audit and visual documentation describe the changes after that report.

The former generic incomplete-reply exception is split by stage. A valid bounded plan can still run when planning text is cut off. Complete grounded sentences are kept on a length stop. If synthesis cannot finish, preserve the scientific tool results and report evidence-only mode. New software changes are in the working copy. The previous verified release ZIP remains the recovery point.
