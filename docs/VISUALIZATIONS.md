# Choosing and exporting visuals

| Question | View in AeroFox | Portable output |
| --- | --- | --- |
| Compare measured values, distributions, time series or solver traces | Interactive Plotly chart. The title, axis units, conditions and provenance come from the scientific tool. | CSV of plotted values and PNG from the Plotly toolbar |
| Compare engineering factors with mixed evidence | Qualitative matrix with conditions and verification steps | CSV |
| Ask what to verify first and what follows from each answer | Decision flowchart with linked branches and evidence cards | Mermaid source (.mmd) |

Try “Show how Saffire-II measured flow differs from the catalog” for measured values. Ask “Mostre um fluxograma de verificação contra incêndio para um traje EVA” for the decision workflow. The workflow is a proposal for verification. Check the actual configuration and atmosphere before selecting a test.

The app renders its decision steps and links directly from the Python result. It does not evaluate Mermaid code supplied in a question. The editable Mermaid file expresses the same decisions and branch labels. This keeps the chat usable offline and lets reviewers use their preferred Mermaid renderer.

## Python and Colab

The checked-in scientific notebook uses Matplotlib for reproducible figures. Continue to use it for saved scientific figures, consistent labels and report reproduction. Use interactive Plotly in the application when exploring traces, comparing samples or inspecting exact axis values. Use Mermaid for decisions and process diagrams. An editable Mermaid file can also go through the official Mermaid CLI to SVG in a local environment.

To regenerate the same decision graph from a checkout or an extracted archive in Colab, use the repository root as the working directory and run:

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("backend").resolve()))
from aerofox.science.workflows import fire_safety_workflow, mermaid_source

workflow = fire_safety_workflow("eva_suit", language="pt")["blocks"][0]
Path("eva-verification.mmd").write_text(mermaid_source(workflow), encoding="utf-8")
```

Render the downloaded file with a Mermaid-compatible editor or the official CLI. The Colab analysis notebook and the app use the same NASA snapshot. The workflow export needs the project source and its installed Python dependencies. It does not need a model call.

- [Mermaid flowchart syntax](https://mermaid.js.org/syntax/flowchart.html)
- [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli)
- [Plotly JavaScript configuration](https://plotly.com/javascript/configuration-options/)
- [Matplotlib figure guide](https://matplotlib.org/stable/users/explain/figure/figure_intro.html)

