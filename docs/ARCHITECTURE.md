# AeroFox architecture

The browser submits one conversation turn to FastAPI. Sessions isolate project parameters, a compact history and downloadable chart artifacts. The local model on a separate loopback listener plans scientific work and synthesizes results. The application continues with an explicitly labeled offline evidence path when inference is unavailable or cannot validate.

    Browser -> FastAPI -> Session -> Independent llama.cpp tool planner
                                 -> Typed allow-listed tools -> NASA snapshot / Python analyses
                                 -> Independent llama.cpp synthesis -> Grounding checks
                                 -> Answer, source cards, figures and CSVs -> Browser

- backend/aerofox/agent/llm.py contains the chat transport, queue, grammar, tool validation and grounded generation.
- backend/aerofox/agent/orchestrator.py coordinates the turn, approved project state, offline recovery, citation cards and session-local artifacts.
- backend/aerofox/agent/tools.py maps public scientific tool names to server-side code. The model cannot write project state, issue shell commands, read arbitrary files, choose URLs or run supplied code.
- backend/aerofox/evidence/store.py combines experiment metadata, structured data, lexical search and applicability notes. The compact NASA snapshot remains usable when upstream is unavailable.
- backend/aerofox/science/analyses.py computes verified tables, experiment comparisons and figures. compartment.py handles the passive transport model and flow balance.
- frontend/app.js renders application-verified blocks and cites available source cards. Plotly is vendored. The main interface remains a single conversation.
- scripts/launch.py and scripts/local_model.py handle cooperative startup and cleanup. Keep model artifacts outside Git and use the pins when changing the model.

Change one component at a time and add a targeted regression to the existing tests. The development reviewer should verify source conditions, units, visible plots and actual inference settings separately from offline checks. See DATA_SOURCES.md, MODEL_RUNTIME.md, SCIENTIFIC_METHODS.md and DEPLOYMENT.md.

