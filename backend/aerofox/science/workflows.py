"""Scoped verification workflows shared by the browser and Mermaid export."""
from __future__ import annotations

from .analyses import AnalysisError


def fire_safety_workflow(system: str, language: str = "en") -> dict:
    # These are engineering review steps. Edges express decisions, not a physical model.
    scopes = {
        "eva_suit": ("EVA suit", "Traje EVA", "breathing circuit, powered wiring and adjacent layers",
                     "circuito respiratório, fiação energizada e camadas vizinhas", "LIT-EVA-WIRE", "LIT-ATM-SUIT"),
        "lunar_habitat": ("Lunar habitat", "Habitat lunar", "cabin equipment, oxygen circuits and escape paths",
                          "equipamentos da cabine, circuitos de oxigênio e rotas de fuga", "LIT-MOON-EXTERIOR", "LIT-ATM-GENERAL"),
        "mars_habitat": ("Mars habitat", "Habitat em Marte", "cabin equipment, oxygen circuits and escape paths",
                         "equipamentos da cabine, circuitos de oxigênio e rotas de fuga", "LIT-MARS-EXTERIOR", "LIT-ATM-GENERAL"),
        "pressurized_rover": ("Pressurized rover", "Rover pressurizado", "battery enclosure, crew compartment and egress",
                             "compartimento da bateria, cabine e saídas", "F05", "LIT-ATM-GENERAL"),
    }
    if system not in scopes:
        raise AnalysisError("Use a supported system: EVA suit, lunar habitat, Mars habitat or pressurized rover.")
    en, pt, focus_en, focus_pt, source, atmosphere = scopes[system]
    if language == "pt":
        title = f"{pt}: verificação de segurança contra incêndio"
        labels = [
            "A atmosfera local foi definida?",
            "Registre pressão, fração de oxigênio e condições de falha.",
            f"Há uma fonte de ignição plausível junto a {focus_pt}?",
            "Identifique falhas elétricas, superfícies quentes e materiais próximos.",
            "Avalie a energia da falha, as barreiras e as condições de ensaio.",
            "O ensaio representa a montagem e a atmosfera reais?",
            "Planeje um ensaio representativo do conjunto instalado.",
            "Registre a evidência, seus limites e os controles avaliados.",
        ]
        yes, no, after = "Sim", "Não", "Em seguida"
        summary = "Comece pela atmosfera local. Depois avalie a fonte de ignição e confira se o ensaio representa o conjunto instalado."
        limit = "Fluxograma para planejar a verificação. A evidência se aplica às condições do ensaio citado."
    else:
        title = f"{en} fire-safety verification workflow"
        labels = [
            "Is the local atmosphere defined?",
            "Record pressure, oxygen fraction and credible fault conditions.",
            f"Is there a credible ignition source near {focus_en}?",
            "Inventory electrical faults, hot surfaces and nearby materials.",
            "Evaluate fault energy, barriers and test conditions.",
            "Does the test represent the installed assembly and atmosphere?",
            "Plan a representative test of the installed assembly.",
            "Record the evidence, its scope and the controls evaluated.",
        ]
        yes, no, after = "Yes", "No", "Then"
        summary = "Start with the local atmosphere. Then assess the ignition source and check whether the test represents the installed assembly."
        limit = "Conceptual verification workflow. Evidence applies to the conditions of the cited test."
    ids = ["atmosphere", "measure", "ignition", "inventory", "controls", "applicability", "test", "record"]
    refs = [[atmosphere], [atmosphere], [source], [], [source], [source], [], []]
    nodes = [{"id": key, "label": label, "decision": key in {"atmosphere", "ignition", "applicability"}, "refs": citations}
             for key, label, citations in zip(ids, labels, refs)]
    edges = [{"from": a, "to": b, "label": text} for a, b, text in (
        ("atmosphere", "ignition", yes), ("atmosphere", "measure", no), ("measure", "ignition", after),
        ("ignition", "controls", yes), ("ignition", "inventory", no), ("inventory", "controls", after),
        ("controls", "applicability", after), ("applicability", "record", yes), ("applicability", "test", no),
    )]
    block = {"type": "flowchart", "id": "verification_workflow", "title": title, "nodes": nodes, "edges": edges,
             "caption": limit, "source": f"AeroFox engineering workflow, {source} and {atmosphere}"}
    return {"summary": summary, "blocks": [block], "evidence": [atmosphere, source], "warnings": [limit],
            "data": {"workflow": title, "checkpoints": labels}}


def mermaid_source(block: dict) -> str:
    identifiers = {node["id"]: f"n{index}" for index, node in enumerate(block["nodes"])}
    # Plain labels only. Mermaid encodes double quotes as a named entity.
    def label(text):
        return " ".join(text.splitlines()).replace('"', "#quot;").replace("|", "#124;")

    lines = ["flowchart TD"]
    for node in block["nodes"]:
        opening, closing = ("{", "}") if node["decision"] else ("[", "]")
        lines.append(f'    {identifiers[node["id"]]}{opening}"{label(node["label"])}"{closing}')
    for edge in block["edges"]:
        lines.append(f'    {identifiers[edge["from"]]} -->|{label(edge["label"])}| {identifiers[edge["to"]]}')
    return "\n".join(lines) + "\n"

