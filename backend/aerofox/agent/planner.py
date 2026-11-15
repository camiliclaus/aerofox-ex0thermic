"""Offline engine: plans tool calls from the deterministic understanding and composes the answer.

It runs whenever the language model is unavailable (no key, provider error, budget
exhausted) and is honest about being template-based. It uses the same tools and
evidence as the model-driven path, so numbers and charts are identical.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..evidence.store import get_store
from .nlu import Understanding
from .state import Session

T = {
    "en": {"offline": "Offline engine (deterministic tools, no language model).", "missing": "To make this more specific, tell me:",
           "limits": "Limits of this answer", "nodata": "I could not find evidence for that in the AeroFox snapshot.",
           "help": ("I am AeroFox. I answer questions about NASA microgravity combustion experiments (FLEX, Saffire, BASS, SAME, CFI, "
                    "ACME) and run preliminary fire-safety analyses: cabin atmospheres, materials, ventilation and smoke transport, "
                    "detection, suppression and lunar/Mars habitat reviews. Every number comes from NASA data or a stated model."),
           "plain": "In plain terms:", "status_head": "What the evidence in my last answer is based on:",
           "uncert_head": "Main uncertainties in the last answer:", "recommend_head": "Before deciding, inspect:",
           "change_head": "Information that would most change the recommendation:",
           "followup": "You can ask me to export the data behind any chart, explain it more simply, or change the scenario."},
    "pt": {"offline": "Motor offline (ferramentas determinísticas, sem modelo de linguagem).",
           "missing": "Para tornar a análise mais específica, informe:", "limits": "Limites desta resposta",
           "nodata": "Não encontrei evidências para isso no snapshot do AeroFox.",
           "help": ("Sou o AeroFox. Respondo perguntas sobre experimentos de combustão em microgravidade da NASA (FLEX, Saffire, BASS, "
                    "SAME, CFI, ACME) e faço análises preliminares de segurança contra incêndio: atmosferas de cabine, materiais, "
                    "ventilação e transporte de fumaça, detecção, supressão e habitats lunares/marcianos. Todo número vem de dados "
                    "da NASA ou de um modelo declarado."),
           "plain": "Em termos simples:", "status_head": "Base das evidências da última resposta:",
           "uncert_head": "Principais incertezas da última resposta:", "recommend_head": "Antes de decidir, examine:",
           "change_head": "Informações que mais mudariam a recomendação:",
           "followup": "Peça para exportar os dados de qualquer gráfico, explicar de forma mais simples ou mudar o cenário. "
                       "(Os resumos técnicos abaixo estão em inglês no modo offline.)"},
}

PLAIN = {
    "fire_safety_factors": {
        "en": "The biggest lever for a habitat's fire risk is the air itself: more oxygen makes almost everything burn more easily, and most "
              "NASA fire tests in space were done in ordinary air. Wiring, batteries and oxygen equipment are where past NASA fires started, "
              "and the crew must be able to get out fast. The table orders these by how much past accidents and missing test data matter, "
              "not by a calculated risk number.",
        "pt": "A maior alavanca do risco de incêndio em um habitat é o próprio ar: mais oxigênio faz quase tudo queimar mais fácil, e a maioria "
              "dos testes da NASA no espaço foi feita em ar comum. Fiação, baterias e equipamentos de oxigênio foram a origem de incêndios "
              "passados da NASA, e a tripulação precisa conseguir sair rápido. A tabela ordena esses fatores pelo histórico de acidentes e "
              "pela falta de testes, não por um número de risco calculado."},
    "assess_atmosphere": {
        "en": "What matters for burning is how much oxygen is available, which depends on both the oxygen percentage and the cabin pressure. "
              "The chart shows where NASA has actually tested flames: if your cabin sits far from the dots, there is no direct test data for it.",
        "pt": "O que importa para a queima é quanto oxigênio está disponível, que depende da porcentagem de oxigênio e da pressão da cabine. "
              "O gráfico mostra onde a NASA realmente testou chamas: se a sua cabine está longe dos pontos, não há dados de teste diretos."},
    "flex035_case_study": {
        "en": "The visible flame disappeared, but the fuel kept 'burning' just as fast in an invisible, cooler way for about 25 seconds. "
              "So 'I can't see a flame' does not mean the fire is over.",
        "pt": "A chama visível sumiu, mas o combustível continuou 'queimando' na mesma velocidade de forma invisível e mais fria por cerca de "
              "25 segundos. Ou seja, 'não vejo chama' não significa que o fogo acabou."},
    "saffire2_flow_case_study": {
        "en": "NASA's table says two fabric samples had the same airflow, but the instruments show the second had 25% more air - and it "
              "burned about 24% faster. Always check the instrument record, not just the summary table.",
        "pt": "A tabela da NASA diz que duas amostras de tecido tiveram o mesmo fluxo de ar, mas os instrumentos mostram que a segunda teve 25% "
              "mais ar - e queimou cerca de 24% mais rápido. Sempre confira o registro dos instrumentos, não só a tabela-resumo."},
    "chart_flex_burning_rate_vs_oxygen": {
        "en": "Each dot is one fuel droplet burned on the Space Station. More oxygen around the droplet makes it burn faster.",
        "pt": "Cada ponto é uma gota de combustível queimada na Estação Espacial. Mais oxigênio ao redor da gota faz ela queimar mais rápido."},
    "smoke_particle_sizes": {
        "en": "Smoke from overheated materials in space is made of very tiny particles (a few tenths of a micrometre), so detectors must be "
              "able to see very small particles.",
        "pt": "A fumaça de materiais superaquecidos no espaço é formada por partículas muito pequenas (alguns décimos de micrômetro), então os "
              "detectores precisam enxergar partículas muito pequenas."},
    "compare_ventilation_designs": {
        "en": "If the battery bay shares air with the crew module, smoke reaches the crew; if it has its own exhaust, it doesn't. This is a "
              "simplified mixing model with example numbers.",
        "pt": "Se o compartimento de baterias compartilha ar com o módulo da tripulação, a fumaça chega à tripulação; se tem exaustão própria, "
              "não chega. É um modelo simplificado de mistura com números de exemplo."},
    "evidence_coverage_matrix": {
        "en": "Dark cells are decisions backed by real measurements in the right conditions; light cells have only indirect evidence; blank "
              "cells have none. Lunar and Mars fire behaviour is mostly blank.",
        "pt": "Células escuras são decisões apoiadas por medições reais nas condições certas; claras têm só evidência indireta; vazias não "
              "têm nenhuma. O comportamento do fogo na Lua e em Marte está quase todo vazio."},
}


@dataclass
class Plan:
    steps: list[tuple[str, dict]] = field(default_factory=list)
    preface: list[str] = field(default_factory=list)
    meta: str | None = None   # simplify | uncertainty | evidence_status | recommend_test | help | export


def make_plan(u: Understanding, s: Session) -> Plan:
    p = Plan()
    I = u.intents
    proj = s.project
    if "greeting" in I or ("help" in I and len(I) <= 2):
        p.meta = "help"
        return p
    if "export" in I:
        p.steps.append(("export_data", {}))
        return p
    if "simplify" in I and s.last_topic:
        p.meta = "simplify"
        return p
    if "uncertainty" in I and s.last_topic and not (u.experiments or u.system):
        p.meta = "uncertainty"
        return p
    if "evidence_status" in I and s.last_topic and not u.experiments:
        p.meta = "evidence_status"
        return p
    if "recommend_test" in I:
        p.meta = "recommend_test"
        p.steps.append(("search_evidence", {"query": u.text, "k": 5}))
        return p

    system = u.system or proj.system
    gravity = u.gravity or proj.gravity
    if "eva" in I:
        system = "eva_suit"
    elif "battery" in I and not u.system:
        system = system or "battery_system"

    if "workflow" in I and system in {"eva_suit", "lunar_habitat", "mars_habitat", "pressurized_rover"}:
        p.steps.append(("fire_safety_workflow", {"system": system, "language": s.language}))
        return p

    # Follow-up: "now change the atmosphere / what if O2 increases" re-runs the last analysis with new values
    if "what_if" in I and s.last_topic and not (u.experiments or u.materials):
        if u.o2_pct is None and u.o2_direction and proj.o2_pct is None:
            p.preface.append("o2_direction_only")
        if s.last_topic in ("fire_safety_factors", "assess_atmosphere") or "atmosphere" in I:
            pressure, oxygen = u.pressure_kPa or proj.pressure_kPa, u.o2_pct or proj.o2_pct
            if pressure and oxygen:
                p.steps.append(("assess_atmosphere", {"pressure": pressure, "pressure_unit": "kPa", "o2": oxygen, "gravity": gravity}))
            if system:
                p.steps.append(("fire_safety_factors", {"system": system, "gravity": gravity, "pressure_kPa": pressure, "o2_pct": oxygen}))
            if u.o2_direction and not p.steps:
                p.steps.append(("chart_flex_burning_rate_vs_oxygen", {}))
            if p.steps:
                return p

    if "ventilation" in I:
        if re.search(r"fail|falh|\boff\b|stop|para(m|r)|loss|perda", u.text.lower()):
            p.preface.append("ventilation_failure")
        p.steps.append(("compare_ventilation_designs", {}))
    if "coverage" in I:
        p.steps.append(("evidence_coverage_matrix", {}))
    if "gravity_compare" in I or (len(set(u.gravities)) >= 2 and "compare" in I):
        p.steps.append(("compare_gravity_regimes", {}))
    for exp in u.experiments[:3]:
        if exp.startswith("FLEX-") and exp != "FLEX-2":
            p.steps.append(("flex035_case_study", {}) if exp == "FLEX-035" else ("flex_run", {"number": int(exp.split("-")[1])}))
            continue
        p.steps.append(("experiment_overview", {"name": exp}))
        e = exp.lower()
        if "saffire-ii" in e or "saffire-2" in e:
            p.steps.append(("saffire2_flow_case_study", {}))
        if e.startswith("same"):
            p.steps.append(("smoke_particle_sizes", {}))
        if e == "flex" and ("chart" in I or "droplet" in I):
            p.steps.append(("chart_flex_burning_rate_vs_oxygen", {}))
    if u.materials:
        p.steps.append(("materials_evidence", {"materials": u.materials}))
    if "flameout" in I and "droplet" not in I and not u.experiments:
        p.steps.append(("flex035_case_study", {}))
    if "droplet" in I and not u.experiments:
        if u.diameter_mm:
            p.steps.append(("droplet_burn_time", {"d0_mm": u.diameter_mm, "fuel": u.fuel or "heptane", "x_o2": (u.o2_pct or 21) / 100}))
        elif "cool" in u.text.lower() or "fria" in u.text.lower() or "extinct" in u.text.lower() or "flameout" in I:
            p.steps.append(("flex035_case_study", {}))
        else:
            p.steps.append(("chart_flex_burning_rate_vs_oxygen", {"fuel": u.fuel}))
    pres = u.pressure_kPa or proj.pressure_kPa
    o2 = u.o2_pct or proj.o2_pct
    if ("atmosphere" in I or "what_if" in I) and pres and o2:
        p.steps.append(("assess_atmosphere", {"pressure": pres, "pressure_unit": "kPa", "o2": o2, "gravity": gravity}))
    elif not system and "atmosphere" in I and o2 is None and pres is None and not p.steps and ("oxygen" in u.text.lower() or "o2" in u.text.lower()
                                                                                  or "oxig" in u.text.lower()):
        p.steps.append(("chart_flex_burning_rate_vs_oxygen", {}))
        p.steps.append(("search_evidence", {"query": "oxygen concentration flammability materials atmosphere", "k": 4}))
    if "detection" in I and not any(t[0] == "smoke_particle_sizes" for t in p.steps):
        p.steps.append(("smoke_particle_sizes", {}))
    if "suppression" in I and not p.steps:
        p.steps.append(("chart_flex_burning_rate_vs_oxygen", {}))
        p.steps.append(("get_evidence", {"ids": ["F04", "F11", "LIT-BASS2-N2"]}))
    design = bool(system) and (not u.experiments or bool(u.system)) and (
        "design_review" in I or "chart" in I or "recommend" in u.text.lower() or "eva" in I or "battery" in I or not p.steps
    )
    if design or ("design_review" in I and gravity in ("lunar", "mars")):
        sysk = system or {"lunar": "lunar_habitat", "mars": "mars_habitat"}.get(gravity or "", "space_station")
        p.steps.insert(0, ("fire_safety_factors", {"system": sysk, "gravity": gravity, "pressure_kPa": pres, "o2_pct": o2}))
    if "chart" in I and not any(st[0] not in ("search_evidence", "get_evidence", "experiment_overview") for st in p.steps):
        if s.last_topic and u.refers_back:
            p.steps.append((s.last_topic, s.last_args.get("_tool_inputs", {})))
        else:
            p.steps.append(("evidence_coverage_matrix", {}))
    if not p.steps:
        p.steps.append(("search_evidence", {"query": u.text, "k": 5}))
    # de-duplicate while keeping order
    seen, steps = set(), []
    for name, args in p.steps:
        key = (name, str(sorted((k, str(v)) for k, v in args.items())))
        if key not in seen:
            seen.add(key)
            steps.append((name, args))
    p.steps = steps[:5]
    return p


def compose(u: Understanding, s: Session, plan: Plan, results: list[dict]) -> str:
    lang = s.language
    L = T[lang]
    store = get_store()
    out: list[str] = []
    if plan.meta == "help":
        return L["help"] + "\n\n" + L["followup"]
    if plan.meta == "simplify":
        txt = PLAIN.get(s.last_topic or "", {}).get(lang)
        return f"**{L['plain']}** " + (txt or (s.turns[-1].text[:500] if s.turns else L["nodata"]))
    if plan.meta in ("uncertainty", "evidence_status"):
        prev_ev = [store.get(e) for e in s.last_args.get("_evidence", []) if store.get(e)]
        if plan.meta == "uncertainty":
            out.append(f"**{L['uncert_head']}**")
            for w in s.last_args.get("_warnings", [])[:5]:
                out.append(f"- {w}")
            for e in prev_ev[:3]:
                if e.limitations:
                    out.append(f"- [{e.id}] {e.limitations}")
            if s.last_topic == "fire_safety_factors":
                out.append("- " + ("The strongest single uncertainty is the flammability of the chosen materials at the habitat's own "
                                   "atmosphere and gravity: no NASA flight test in the snapshot covers it." if lang == "en" else
                                   "A maior incerteza é a inflamabilidade dos materiais escolhidos na atmosfera e gravidade do próprio "
                                   "habitat: nenhum teste em voo da NASA no snapshot cobre essa condição."))
        else:
            out.append(f"**{L['status_head']}**")
            for e in prev_ev:
                out.append(f"- [{e.id}] {e.card()['status']}: {e.text[:160]}")
        return "\n".join(out)
    if plan.meta == "recommend_test":
        out.append(f"**{L['recommend_head']}**")
        for r in results:
            for item in (r.get("data", {}).get("results") or [])[:5]:
                out.append(f"- [{item['id']}] {item['title'][:90]} — {item['text'][:150]}")
        miss = s.project.missing_for_design_review()
        out.append(f"\n**{L['change_head']}**")
        out += [f"- {m}" for m in (miss or ["the materials' flammability at your design atmosphere (no flight data, F09)",
                                            "measured air speeds near potential ignition sources"])]
        return "\n".join(out)
    if "o2_direction_only" in plan.preface:
        out.append("Raising oxygen generally increases flammability (LIT-ATM-GENERAL); in FLEX, each +0.1 in O2 mole fraction raised "
                   "droplet burning rates by about 0.16–0.19 mm²/s (F03). Give me the new O2 level and pressure to compare it with "
                   "your current design." if lang == "en" else
                   "Aumentar o oxigênio geralmente aumenta a inflamabilidade (LIT-ATM-GENERAL); no FLEX, cada +0,1 na fração molar de "
                   "O2 aumentou a taxa de queima das gotas em cerca de 0,16–0,19 mm²/s (F03). Informe o novo nível de O2 e a pressão "
                   "para comparar com o projeto atual.")
    if "ventilation_failure" in plan.preface:
        out.append("If ventilation stops in microgravity, there is no buoyant flow: a flame is fed only by diffusion and may weaken, "
                   "but smoke also stops moving toward detectors in other compartments, so detection can be delayed. Below, a "
                   "synthetic mixing model shows how compartment connectivity controls where smoke goes."
                   if lang == "en" else
                   "Se a ventilação parar em microgravidade, não há fluxo por empuxo: a chama é alimentada só por difusão e pode "
                   "enfraquecer, mas a fumaça também deixa de ir até detectores em outros compartimentos, atrasando a detecção. "
                   "Abaixo, um modelo sintético de mistura mostra como a conexão entre compartimentos controla a fumaça.")
    if "gravity_compare" in plan.preface:
        out.append("Orbital microgravity removes buoyancy; lunar gravity (1.62 m/s²) keeps a weak buoyant flow. Flame spread is not "
                   "monotonic in gravity, so lunar behaviour cannot be interpolated between orbit and Earth (F10)."
                   if lang == "en" else
                   "A microgravidade orbital elimina o empuxo; a gravidade lunar (1,62 m/s²) mantém um fluxo fraco. A propagação de "
                   "chama não é monotônica com a gravidade, então o comportamento lunar não pode ser interpolado entre órbita e Terra (F10).")
    any_ok = False
    for r in results:
        if not r.get("ok"):
            out.append(("⚠ " if True else "") + f"{r.get('tool')}: {r.get('error')}")
            continue
        any_ok = True
        if r["tool"] in ("search_evidence", "get_evidence"):
            items = r["data"].get("results") or r["data"].get("items") or []
            for it in items[:4]:
                out.append(f"- **{it['title'][:90]}** [{it['id']}]: {it['text'][:260]}")
            if not items:
                out.append(L["nodata"])
            continue
        out.append(r["summary"])
        if r["tool"] == "fire_safety_factors":
            for f in r["data"]["factors"][:5]:
                out.append(f"- **{f['short']}** (tier {f['tier']}, evidence: {f['coverage']}): {f['why']}")
    warnings = []
    for r in results:
        for w in r.get("warnings", []) if r.get("ok") else []:
            if w not in warnings:
                warnings.append(w)
    if warnings:
        out.append(f"\n**{L['limits']}:**")
        out += [f"- {w}" for w in warnings[:6]]
    miss = s.project.missing_for_design_review()
    if any(r.get("tool") == "fire_safety_factors" and r.get("ok") for r in results) and miss:
        out.append(f"\n{L['missing']} " + "; ".join(miss) + ".")
    if not any_ok and not out:
        out.append(L["nodata"])
    return "\n\n".join(x for x in out if x)
