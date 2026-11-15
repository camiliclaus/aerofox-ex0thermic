"""Deterministic language understanding (English and Portuguese).

Used in two ways: (1) by the offline engine to plan tool calls, and (2) on every
turn, with or without the language model, to extract explicit quantities and
project facts into typed state. It recognises intent families rather than
phrases, and allows several intents in one message.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..science.analyses import resolve_experiment, resolve_system
from ..science.units import UnitError, to_kpa


def fold(text: str) -> str:
    """Lower-case and strip accents so 'oxigênio' and 'oxigenio' match."""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


PT_MARKERS = {"que", "qual", "quais", "como", "para", "uma", "um", "voce", "você", "faca", "faça", "grafico", "gráfico", "sobre",
              "nao", "isso", "esse", "essa", "projeto", "explique", "comparar", "por", "favor", "deveria",
              "devo", "fogo", "incendio", "incêndio", "oxigenio", "oxigênio", "seguranca", "segurança", "mais", "simples",
              "agora", "mude", "dados", "experimento", "experimentos", "marte", "não", "também", "também", "quero", "qual"}
EN_MARKERS = {"the", "what", "which", "how", "should", "chart", "about", "please", "explain", "compare", "data", "fire",
              "safety", "oxygen", "now", "change", "simpler", "experiment", "is", "are", "of", "and"}

INTENT_PATTERNS = {
    "workflow": r"\b(flow\s*chart|decision tree|fluxogram\w*|arvore de decisao|mermaid|mermaide)\b",
    "chart": r"\b(chart|graph|plot|visuali[sz]|diagram|figure|grafico|plote|plotar|visualiza|matrix|matriz|curve|curva)\w*",
    "compare": r"\b(compar\w*|versus|vs\.?|difference|diferen\w*|contrast)\b",
    "design_review": r"\b(revis\w*|seguranca contra incendio|design\w*|projet\w*|projeto|planning|plan\w*|build\w*|construi\w*|habitat|base\b|review|factors?|fatores?|consider|considerar|recommend\w*|recomend\w*|protect\w*|prote\w*|fire protection|seguranca contra)",
    "what_if": r"\b(what if|what happens|what changes|e se|o que acontece|o que muda|increase[sd]?|decrease[sd]?|aument\w*|diminu\w*|now change|agora mude|mude|change the|altere)\b",
    "export": r"\b(export\w*|download\w*|csv|baixar|exportar|data behind|dados por tras|raw data)\b",
    "uncertainty": r"\b(uncertain\w*|incerte\w*|confidence|confian\w*|how sure|limitation\w*|limitac\w*|weakest|strongest uncertainty|maior incerteza)\b",
    "simplify": r"\b(simpler|simple terms|simply|eli5|plain language|mais simples|termos simples|simplifi\w*|leigo)\b",
    "evidence_status": r"\b(actual measurements?|based on (actual )?measure\w*|measured|medic\w*|medido\w*|real data|dados reais|which findings)\b",
    "recommend_test": r"\b(which experiment should|what experiment should|inspect before|qual experimento devo|what (information|data) would (most )?change|o que mudaria|most change|missing data|dados faltantes)\b",
    "ventilation": r"\b(ventilat\w*|ventila\w*|airflow|air flow|fluxo de ar|fans?|ventilador\w*|hvac|smoke spread|compartment\w*|compartiment\w*|bays?|baias?|duct)\b",
    "atmosphere": r"\b(atmospher\w*|atmosfer\w*|pressure|pressao|psi|kpa|oxygen concentration|concentracao de oxigenio|o2|oxygen|oxigenio)\b",
    "materials": r"\b(material\w*|silicone|pmma|acrylic|nomex|kapton|teflon|sibal|cotton|fabric|tecido|pyrell|delrin|foam|espuma)\b",
    "droplet": r"\b(droplet\w*|gota\w*|liquid fuel|combustivel liquido|burning rate|taxa de queima|d2|d\^2|d-squared|cool flame\w*|chama fria)\b",
    "flameout": r"(no longer visible|not visible|invisible|after the (visible )?flame|flame[- ]?out|nao e mais visivel|chama (visivel )?apag\w*|depois que a chama|keep burning|continuar queimando|continue burning)",
    "detection": r"\b(smoke|fumaca|detect\w*|detec\w*|alarm\w*|alarme|particle\w*|particula\w*|aerosol\w*)\b",
    "suppression": r"\b(suppress\w*|supress\w*|extinguish\w*|extingu\w*|extinction|extincao|inert\w*|co2 dilution|helium|helio)\b",
    "coverage": r"\b(coverage|cobertura|evidence gap\w*|lacuna\w*|which evidence|what evidence|what data (do you|exist)|evidence map)\b",
    "explain": r"\b(what (is|was|did|does)|explain|explique|o que (e|foi|mediu)|tell me about|describe|descreva|measure[ds]?|mediu|summar\w*|resum\w*|how does|como (o|a) )\b",
    "help": r"\b(help|ajuda|what can you do|o que voce faz|capabilities)\b",
    "greeting": r"^\s*(hi|hello|hey|ola|oi|bom dia|boa tarde|good (morning|afternoon))\b[\s!.?]*$",
    "eva": r"\b(eva|spacesuit|space suit|traje)\b",
    "battery": r"\b(batter\w*|bateria\w*|lithium|litio)\b",
    "gravity_compare": r"(\b(lunar gravity|gravidade lunar|microgravity|microgravidade|partial gravity|gravidade parcial).{0,40}\b(lunar|moon|lua|micro\w*|orbit\w*|mars|marte)\b|partial gravity|gravidade parcial)",
}

GRAVITY_PATTERNS = [("lunar", r"\b(lunar|moon|lua)\b"), ("mars", r"\b(mars|martian|marte|marciano)\b"),
                    ("micro", r"\b(microgravity|microgravidade|orbit\w*|iss|space station|estacao espacial|cygnus)\b"),
                    ("earth", r"\b(earth gravity|1 ?g\b|normal gravity|terra)\b")]

MATERIAL_WORDS = ["silicone", "pmma", "acrylic", "nomex", "kapton", "teflon", "sibal", "cotton", "pyrell", "delrin", "cellulose",
                  "paper", "lampwick", "kevlar", "polyethylene", "foam", "velcro", "nylon", "polycarbonate", "polyimide"]


CANONICAL = {"PSI-69": "FLEX", "PSI-68": "FLEX-2", "PSI-98": "SAFFIRE-I", "PSI-99": "SAFFIRE-II", "PSI-100": "SAFFIRE-III",
             "PSI-26": "BASS", "PSI-25": "BASS-II", "PSI-102": "SAME", "PSI-101": "SAME-R", "PSI-47": "DAFT", "PSI-39": "CFI",
             "PSI-159": "CFI-G", "PSI-21": "ACME", "PSI-107": "SPICE", "PSI-106": "SLICE"}


@dataclass
class Understanding:
    text: str
    language: str = "en"
    intents: set[str] = field(default_factory=set)
    experiments: list[str] = field(default_factory=list)
    system: str | None = None
    gravity: str | None = None
    gravities: list[str] = field(default_factory=list)
    pressure_kPa: float | None = None
    o2_pct: float | None = None
    o2_direction: str | None = None          # "up" / "down" for relative changes
    materials: list[str] = field(default_factory=list)
    fuel: str | None = None
    diameter_mm: float | None = None
    refers_back: bool = False

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["intents"] = sorted(self.intents)
        return d


def detect_language(text: str) -> str:
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    pt = sum(w in PT_MARKERS for w in words) + 2 * bool(re.search(r"[ãõçáéíóúâêô]", text.lower()))
    en = sum(w in EN_MARKERS for w in words)
    return "pt" if pt > en else "en"


def explicit_language(text: str) -> str | None:
    language = re.search(r"\b(?:in english|em ingles|in portuguese|em portugues)\b", fold(text))
    if language:
        return "en" if language[0] in {"in english", "em ingles"} else "pt"
    return None


def understand(text: str) -> Understanding:
    raw = text.strip()
    t = fold(raw)
    u = Understanding(text=raw, language=detect_language(raw))
    for name, pat in INTENT_PATTERNS.items():
        if re.search(pat, t):
            u.intents.add(name)
    # experiments: scan for known names
    seen_acc = set()
    for m in re.finditer(r"(flame extinguishment|burning and suppression of solids|smoke aerosol measurement|smoke and aerosol measurement|"
                         r"dust and aerosol|advanced combustion via microgravity|smoke point in co-flow|structure and liftoff|"
                         r"solid fuel ignition and extinction|saffire[\s-]?(?:iii|ii|i|[1-6])|flex[\s-]?2|flex[\s-]?0?\d{2,3}|flex|"
                         r"bass[\s-]?ii|bass|same[\s-]?r|same|daft|cfi[\s-]?g|cfi|cool flames? investigation|acme|spice|slice|sofie|psi-\d+)", t):
        name = m.group(0)
        if name == "same" and not (
            re.search(r"\bSAME\b", raw) or re.search(r"\b(?:same experiment|experimento same)\b", t)
        ):
            continue
        if re.fullmatch(r"flex[\s-]?0?\d{2,3}", name) and not re.fullmatch(r"flex[\s-]?2", name):
            label = "FLEX-" + re.sub(r"\D", "", name).zfill(3)
            if label not in u.experiments:
                u.experiments.append(label)
            continue
        if "sofie" in name or "solid fuel ignition" in name:
            if "SOFIE" not in u.experiments:
                u.experiments.append("SOFIE")
            continue
        acc = resolve_experiment(name)
        if acc and acc not in seen_acc:
            seen_acc.add(acc)
            u.experiments.append(CANONICAL.get(acc, acc))
    u.system = resolve_system(t)
    for g, pat in GRAVITY_PATTERNS:
        if re.search(pat, t):
            u.gravities.append(g)
    if u.gravities:
        u.gravity = u.gravities[0]
    elif u.system in ("lunar_habitat", "pressurized_rover"):
        u.gravity = "lunar"
    elif u.system == "mars_habitat":
        u.gravity = "mars"
    if (not u.system and len(u.gravities) == 1 and u.gravity in {"lunar", "mars"}
            and re.search(r"\b(outpost|habitat|base|posto avancado)\b", t)):
        u.system = f"{u.gravity}_habitat"
    pm = re.search(r"(?<![\w.])([-−]?\d+(?:[.,]\d+)?)\s*(kpa|psia|psi|atm|bar|mmhg|torr|mbar)\b", t)
    if pm:
        try:
            pressure = to_kpa(float(pm.group(1).replace("−", "-").replace(",", ".")), pm.group(2))
            if 5 <= pressure <= 1000:
                u.pressure_kPa = round(pressure, 2)
        except UnitError:
            pass
    t = re.sub(r"(\d)\s*(percent|per cent|por cento|pct)\b", r"\1%", t)
    om = (re.search(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:de\s+)?(?:o2|oxygen|oxigenio|o₂)", t)
          or re.search(r"(?:o2|oxygen|oxigenio)\D{0,25}?(\d+(?:[.,]\d+)?)\s*%", t)
          or re.search(r"(\d+(?:[.,]\d+)?)\s*%", t) if re.search(r"o2|oxygen|oxigenio|atmospher|atmosfer", t) else None)
    if om:
        v = float(om.group(1).replace(",", "."))
        if 0 < v <= 100:
            u.o2_pct = v
    xm = re.search(r"x_?o2\s*=?\s*(0?\.\d+)", t)
    if xm and u.o2_pct is None:
        u.o2_pct = round(100 * float(xm.group(1)), 2)
    if re.search(r"\b(increase|higher|more|raise|aument\w*|maior|mais)\b.{0,30}\b(o2|oxygen|oxigenio)", t) or \
       re.search(r"\b(o2|oxygen|oxigenio)\b.{0,30}\b(increase\w*|rises?|goes up|aument\w*|sobe)", t):
        u.o2_direction = "up"
    elif re.search(r"\b(decrease|lower|less|reduce|diminu\w*|menor|menos|reduz\w*)\b.{0,30}\b(o2|oxygen|oxigenio)", t):
        u.o2_direction = "down"
    u.materials = [m for m in MATERIAL_WORDS if re.search(rf"\b{m}\b", t)]
    if re.search(r"\bheptan", t):
        u.fuel = "heptane"
    elif re.search(r"\bmethanol|metanol", t):
        u.fuel = "methanol"
    dm = re.search(r"(\d+(?:[.,]\d+)?)\s*mm\b", t)
    if dm and "droplet" in u.intents | {"droplet"}:
        u.diameter_mm = float(dm.group(1).replace(",", "."))
    u.refers_back = bool(re.search(r"\b(that|this|it|those|the (chart|graph|plot|result|answer|recommendation|same|suit)|isso|esse|essa|este|esta|"
                                    r"aquilo|o grafico|a resposta|anterior|previous|above|acima|again|de novo)\b", t))
    if u.o2_pct is not None or u.pressure_kPa is not None:
        u.intents.add("atmosphere")
    if len(set(u.gravities)) >= 2 and not u.system:
        u.intents.add("gravity_compare")
    return u
