# Start AeroFox

1. Install Python 3.11 or 3.12. On Windows install the x64 build and add Python to PATH.
2. Extract the complete release. Double-click START_AEROFOX.bat on Windows. Leave its console open. On first launch, it downloads the Python dependencies and the pinned model for the available hardware. The app opens automatically.
3. Ask a question. Each response identifies the actual model or the offline recovery. Select NASA datasets or References to browse the snapshot.

For an accurate demonstration, try these in separate chats unless a follow-up is indicated.

- “Why does the curve keep descending after visible extinction in FLEX-035?”
- “Chart the main fire-safety factors for a lunar outpost.” Follow with “And on Mars?”
- “Show the independent measurements for Saffire-II flow, especially sample 2-6.”
- “If I isolate the battery bay, how does contamination transport change? Show a synthetic example.”
- “Mostre um gráfico da relação entre oxigênio e taxa de queima nas gotas do FLEX.”

For the CPU profile run START_AEROFOX.bat --model-profile cpu. For deliberate recovery-mode tests use --offline. For non-Windows and custom endpoints see docs/MODEL_RUNTIME.md. To give the judges a browser link, follow docs/DEPLOYMENT.md.

## Notebook

Upload notebooks/AeroFox_Comprehensive_Data_Analysis.ipynb to Google Colab, select Runtime then Run all. If the verified team repository is unavailable, upload the release ZIP when the notebook asks. Work through the figures in the notebook and review the scope and provenance labels. Save outputs before a Colab session resets.

## Team edits

Read docs/ARCHITECTURE.md and TEAM_GUIDE.md before modifying code or model pins. See CODEX_HANDOFF.md for the active acceptance and test records. Reported measurements and engineering models use the retained data snapshot 2026-11-14.1.

