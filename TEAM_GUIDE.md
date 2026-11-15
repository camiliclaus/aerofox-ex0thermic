# AeroFox team guide

Share the release ZIP and its SHA-256 sidecar. On Windows use START_AEROFOX.bat in the extracted folder. Connect the repository to a team-owned GitHub remote with the team's desired repository visibility. Prefer branches and reviewed changes.

| Work | Edit |
| --- | --- |
| Model configuration and pins | scripts/local_model.py, backend/aerofox/config.py, .env.example |
| Tool planning, grounding and response generation | backend/aerofox/agent/llm.py |
| Chat state and exact identifiers | backend/aerofox/agent/orchestrator.py, state.py, nlu.py |
| Deterministic tools and evidence | backend/aerofox/agent/tools.py, science/, evidence/ |
| User interface | frontend/app.js, index.html and styles.css |
| Experiment intake and provenance | backend/aerofox/ingest/, data/raw/psi/manifest.json |
| Technical report and notebook | scripts/build_report.js and scripts/build_notebook.py |

Install requirements-dev.txt for development. Run python -m pytest -q, the offline scenario benchmark and the real /api/chat model benchmark. Run the Chromium tests to verify browser artifacts before publishing. Keep local model archives, private input and machine caches out of the repo.

Use the pinned CPU or GPU workflow in docs/MODEL_RUNTIME.md when you compare a model. Compare outputs from the same questions and snapshot. Track whether each turn ran real inference, tool calls, evidence, artifacts and latency. A passing offline result stays an offline result.

Tag a successful release. Build a ZIP using scripts/package_release.py and attach its checksum to the team repository's release. To roll back, extract the previous verified ZIP or check out the prior tag, keep model pins aligned, and reopen the launcher. Test /api/health, a measured chart and a design follow-up before sharing the tunnel.

