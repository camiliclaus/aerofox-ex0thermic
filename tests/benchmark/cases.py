"""AeroFox scenario benchmark definitions.

Single-turn: TOPICS maps a topic to (expected tools [any of], expected block types [all of], phrasings by style).
Styles: 'en' plain English, 'enx' paraphrased/technical/ambiguous English, 'pt' Portuguese.
A scenario family = (topic, style) -> 40 topics x 3 styles = 120 families.
Multi-turn: 45 generated conversations with per-turn expectations and state checks.
Holdout: 30 hand-written questions kept out of development (see HOLDOUT note in TESTING.md).
"""

TOPICS = {
    "flex_explain": (["experiment_overview"], ["table"], {
        "en": ["What did the FLEX experiment measure?", "Tell me about FLEX.", "Describe the Flame Extinguishment Experiment."],
        "enx": ["FLEX on the ISS - objectives and hardware?", "Summarise PSI-69 for me", "what was flex trying to find out"],
        "pt": ["O que o experimento FLEX mediu?", "Explique o FLEX", "Resuma o experimento FLEX"]}),
    "flex_o2": (["chart_flex_burning_rate_vs_oxygen"], ["chart"], {
        "en": ["How does oxygen affect droplet burning rate in FLEX?", "Plot FLEX burning rate against oxygen"],
        "enx": ["Show K vs X_O2 for the droplet tests", "droplet burning rate oxygen dependence chart"],
        "pt": ["Como o oxigênio afeta a taxa de queima das gotas no FLEX?", "Faça um gráfico da taxa de queima das gotas versus oxigênio"]}),
    "flex035": (["flex035_case_study"], ["chart"], {
        "en": ["What happened after the visible flame went out in FLEX-035?", "Investigate FLEX-035"],
        "enx": ["FLEX 035 droplet diameter after extinction", "Show the FLEX-035 d-squared curve"],
        "pt": ["O que aconteceu depois que a chama visível apagou no FLEX-035?", "Investigue o FLEX-035"]}),
    "cool_flame": (["flex035_case_study"], ["chart"], {
        "en": ["Can a droplet keep burning after the flame is no longer visible?", "What is a cool flame in droplet combustion?"],
        "enx": ["droplet extinction then cool flame - evidence?", "is visible extinction the end of droplet burning"],
        "pt": ["Uma gota pode continuar queimando depois que a chama não é mais visível?", "O que é uma chama fria na combustão de gotas?"]}),
    "saffire2": (["saffire2_flow_case_study"], ["chart", "table"], {
        "en": ["Compare Saffire-II runs 2-5 and 2-6", "Were Saffire-II samples 2-5 and 2-6 tested at the same airflow?"],
        "enx": ["saffire ii airflow measured vs nominal", "Saffire-2 sample 2-6 flow speed"],
        "pt": ["Compare as amostras 2-5 e 2-6 do Saffire-II", "O fluxo de ar das amostras do Saffire-II foi o mesmo?"]}),
    "saffire": (["experiment_overview"], ["table"], {
        "en": ["What was the Saffire-I experiment?", "Tell me about Saffire-III"],
        "enx": ["Saffire I objectives", "large scale fire in Cygnus Saffire-III summary"],
        "pt": ["O que foi o experimento Saffire-I?", "Fale sobre o Saffire-III"]}),
    "bass": (["experiment_overview"], ["table"], {
        "en": ["What was BASS-II?", "Describe the Burning and Suppression of Solids experiment BASS"],
        "enx": ["BASS-II glovebox tests summary", "PSI-25 overview"],
        "pt": ["O que foi o BASS-II?", "Explique o experimento BASS"]}),
    "same": (["smoke_particle_sizes"], ["chart"], {
        "en": ["How big are smoke particles from overheated spacecraft materials?", "Show smoke particle sizes from SAME-R"],
        "enx": ["SAME-R aerosol AMD by material", "smoke particle diameter chart"],
        "pt": ["Qual o tamanho das partículas de fumaça de materiais superaquecidos?", "Mostre o tamanho das partículas de fumaça do SAME-R"]}),
    "detection": (["smoke_particle_sizes"], ["chart"], {
        "en": ["What should a spacecraft smoke detector be able to see?", "How do I choose smoke detectors for a habitat?"],
        "enx": ["detector sensitivity requirements smoke particles", "fire detection in microgravity data"],
        "pt": ["O que um detector de fumaça de nave precisa detectar?", "Como escolher detectores de fumaça para um habitat?"]}),
    "lunar_review": (["fire_safety_factors"], ["matrix"], {
        "en": ["I'm designing a lunar habitat. What are the main fire safety factors I should consider?", "Fire safety review for a Moon base"],
        "enx": ["lunar outpost fire protection considerations", "planning a base on the moon - fire hazards?"],
        "pt": ["Estou projetando um habitat lunar. Quais fatores de segurança contra incêndio devo considerar?", "Revisão de segurança contra incêndio para uma base lunar"]}),
    "lunar_chart": (["fire_safety_factors"], ["matrix"], {
        "en": ["Do a chart about the main factor on fire safety I should consider while projecting a lunar base.", "Make a chart of the most important fire safety factors for a lunar habitat"],
        "enx": ["graph the key fire risks for my moon base", "visualize lunar base fire safety priorities"],
        "pt": ["Faça um gráfico sobre o principal fator de segurança contra incêndio para uma base lunar", "Gere um gráfico dos fatores de incêndio mais importantes para um habitat lunar"]}),
    "mars_review": (["fire_safety_factors"], ["matrix"], {
        "en": ["How should I design fire protection for a Mars habitat?", "What fire risks matter for a Mars base?"],
        "enx": ["martian habitat fire safety design", "Mars base fire hazards and evidence"],
        "pt": ["Como projetar a proteção contra incêndio de um habitat em Marte?", "Quais riscos de incêndio importam para uma base em Marte?"]}),
    "station_review": (["fire_safety_factors"], ["matrix"], {
        "en": ["What fire safety factors matter most on a space station?", "Review fire safety for an orbital station"],
        "enx": ["ISS-like station fire protection priorities", "space station fire hazards ranking"],
        "pt": ["Quais fatores de segurança contra incêndio importam numa estação espacial?", "Revise a segurança contra incêndio de uma estação orbital"]}),
    "rover": (["fire_safety_factors"], ["matrix"], {
        "en": ["Fire safety for a pressurized rover?", "What should I consider for fire safety in a pressurized rover?"],
        "enx": ["pressurized lunar rover fire hazards", "rover cabin fire protection"],
        "pt": ["Segurança contra incêndio em um rover pressurizado?", "O que considerar sobre incêndio em um veículo pressurizado rover?"]}),
    "eva": (["fire_safety_factors"], ["matrix"], {
        "en": ["What would you recommend for an EVA suit?", "Fire safety considerations for a spacesuit"],
        "enx": ["EVA suit oxygen fire risk", "space suit flammability concerns"],
        "pt": ["O que você recomendaria para um traje EVA?", "Riscos de incêndio em um traje espacial"]}),
    "battery": (["fire_safety_factors", "compare_ventilation_designs"], ["matrix"], {
        "en": ["How should I protect a battery compartment from fire?", "Battery fire safety in a habitat"],
        "enx": ["lithium battery bay fire design", "batteries thermal runaway spacecraft"],
        "pt": ["Como proteger um compartimento de baterias contra incêndio?", "Segurança contra incêndio de baterias em um habitat"]}),
    "atm_psi": (["assess_atmosphere"], ["chart", "table"], {
        "en": ["Assess a cabin atmosphere of 8.2 psi and 34% oxygen", "Is 8.2 psi with 34% O2 covered by NASA tests?"],
        "enx": ["8.2 psia 34% O2 atmosphere evaluation", "pO2 for 8.2 psi at 34 percent oxygen"],
        "pt": ["Avalie uma atmosfera de 8.2 psi e 34% de oxigênio", "8.2 psi com 34% de O2 foi testado pela NASA?"]}),
    "atm_kpa": (["assess_atmosphere"], ["chart", "table"], {
        "en": ["Evaluate 70 kPa with 26.5% oxygen", "What is the oxygen partial pressure at 66.2 kPa and 28.5% O2?"],
        "enx": ["70 kpa 26.5 % o2 coverage", "assess 1 atm 30% oxygen atmosphere"],
        "pt": ["Avalie 70 kPa com 26.5% de oxigênio", "Qual a pressão parcial de oxigênio a 66.2 kPa e 28.5% de O2?"]}),
    "oxygen_general": (["chart_flex_burning_rate_vs_oxygen", "search_evidence", "assess_atmosphere"], [], {
        "en": ["How does oxygen concentration affect the flammability of materials in space?", "What changes if oxygen concentration increases?"],
        "enx": ["more O2 more fire? evidence", "effect of oxygen enrichment on flammability"],
        "pt": ["Como a concentração de oxigênio afeta a inflamabilidade dos materiais no espaço?", "O que muda se a concentração de oxigênio aumentar?"]}),
    "gravity": (["compare_gravity_regimes"], ["chart", "table"], {
        "en": ["Compare orbital microgravity with lunar gravity.", "How does fire behave in lunar gravity compared with microgravity?"],
        "enx": ["moon gravity vs orbit flame spread", "partial gravity vs microgravity flames"],
        "pt": ["Compare a microgravidade orbital com a gravidade lunar", "Como o fogo se comporta na gravidade lunar comparado à microgravidade?"]}),
    "materials_cmp": (["materials_evidence"], ["table"], {
        "en": ["Can we compare silicone and PMMA?", "Which is more flammable in microgravity, silicone or PMMA?"],
        "enx": ["silicone vs pmma microgravity data", "compare Nomex and SIBAL fabric evidence"],
        "pt": ["Podemos comparar silicone e PMMA?", "Qual é mais inflamável em microgravidade, silicone ou PMMA?"]}),
    "materials_one": (["materials_evidence"], ["table"], {
        "en": ["Which NASA experiments are most relevant to Kapton?", "What do we know about Teflon smoke?"],
        "enx": ["kapton evidence", "teflon pyrolysis smoke data"],
        "pt": ["Quais experimentos da NASA são relevantes para Kapton?", "O que sabemos sobre a fumaça do Teflon?"]}),
    "ventilation": (["compare_ventilation_designs"], ["chart"], {
        "en": ["Compare ventilation designs for a battery bay: connected versus isolated compartments.", "How does ventilation affect smoke spread between compartments?"],
        "enx": ["compartment smoke transport model", "isolated vs connected bays airflow"],
        "pt": ["Compare projetos de ventilação: compartimentos conectados versus isolados", "Como a ventilação afeta a fumaça entre compartimentos?"]}),
    "vent_fail": (["compare_ventilation_designs"], ["chart"], {
        "en": ["What happens if the ventilation system fails?", "What if the fans stop during a fire?"],
        "enx": ["ventilation failure smoke detection microgravity", "loss of airflow during a fire"],
        "pt": ["O que acontece se a ventilação falhar?", "E se os ventiladores pararem durante um incêndio?"]}),
    "coverage": (["evidence_coverage_matrix"], ["matrix"], {
        "en": ["What evidence gaps exist for spacecraft fire safety?", "Which evidence supports which engineering decisions?"],
        "enx": ["evidence coverage map", "what data exist and what is missing"],
        "pt": ["Quais lacunas de evidência existem para segurança contra incêndio?", "Mostre a cobertura de evidências"]}),
    "droplet_calc": (["droplet_burn_time"], ["chart"], {
        "en": ["How long does a 3 mm heptane droplet burn?", "Burn time of a 2 mm methanol droplet in air"],
        "enx": ["d2 law burnout 4 mm heptane droplet", "droplet 1.5 mm heptane burning time"],
        "pt": ["Quanto tempo queima uma gota de heptano de 3 mm?", "Tempo de queima de uma gota de metanol de 2 mm"]}),
    "suppression": (["chart_flex_burning_rate_vs_oxygen", "get_evidence", "search_evidence"], [], {
        "en": ["How effective is CO2 or helium dilution at suppressing fires?", "What does NASA data say about fire suppression with inert gases?"],
        "enx": ["helium vs nitrogen diluent extinction", "inerting effectiveness microgravity"],
        "pt": ["Quão eficaz é a diluição com CO2 ou hélio para suprimir incêndios?", "O que os dados da NASA dizem sobre supressão com gases inertes?"]}),
    "apollo1": (["search_evidence"], [], {
        "en": ["What happened in Apollo 1 and what does it teach about cabin fires?", "Lessons from the Apollo 1 fire"],
        "enx": ["apollo 1 pure oxygen fire lessons", "AS-204 fire cause"],
        "pt": ["O que aconteceu na Apollo 1 e o que ensina sobre incêndios em cabine?", "Lições do incêndio da Apollo 1"]}),
    "mir": (["search_evidence"], [], {
        "en": ["What can we learn from the Mir oxygen generator fire?", "Mir 1997 fire lessons"],
        "enx": ["oxygen candle fire station", "Mir fire egress blocked"],
        "pt": ["O que aprendemos com o incêndio do gerador de oxigênio da Mir?", "Lições do incêndio da Mir em 1997"]}),
    "cfi": (["experiment_overview"], ["table"], {
        "en": ["What did the Cool Flames Investigation study?", "Tell me about CFI"],
        "enx": ["cool flames investigation ISS", "PSI-39 summary"],
        "pt": ["O que a investigação de chamas frias CFI estudou?", "Fale sobre o CFI"]}),
    "acme": (["experiment_overview"], ["table"], {
        "en": ["What is ACME?", "Describe the ACME gaseous flame experiments"],
        "enx": ["ACME coflow laminar diffusion flames", "Advanced Combustion via Microgravity Experiments overview"],
        "pt": ["O que é o ACME?", "Descreva os experimentos de chamas gasosas ACME"]}),
    "sofie": (["experiment_overview"], [], {
        "en": ["What is SoFIE?", "Do you have SoFIE data?"],
        "enx": ["Solid Fuel Ignition and Extinction SoFIE results", "sofie flammability exploration atmospheres"],
        "pt": ["O que é o SoFIE?", "Você tem dados do SoFIE?"]}),
    "recommend_test": (["search_evidence"], [], {
        "en": ["Which experiment should I inspect before making this engineering decision?", "What information would most change your recommendation?"],
        "enx": ["what data would most change the recommendation", "which experiment should I inspect first"],
        "pt": ["Qual experimento devo examinar antes de tomar essa decisão de engenharia?", "O que mudaria sua recomendação?"]}),
    "help": ([], [], {
        "en": ["Hello", "What can you do?"], "enx": ["hi", "help"], "pt": ["Olá", "O que você faz?"]}),
    "offtopic": (["search_evidence"], [], {
        "en": ["What is the weather on Mars?", "Who won the football game?"],
        "enx": ["asdf qwerty", "tell me a joke about rockets"],
        "pt": ["Qual o clima em Marte?", "Quem ganhou o jogo de futebol?"]}),
    # fresh session: correct behaviour is to say there is nothing to export yet (no download block)
    "export_empty": (["export_data"], [], {
        "en": ["Export the data", "Can you export the data behind that graph?"],
        "enx": ["download csv", "give me the raw data"],
        "pt": ["Exportar os dados", "Baixar o CSV"]}),
    "spice": (["experiment_overview"], ["table"], {
        "en": ["What was SPICE?", "Tell me about the Smoke Point In Co-flow Experiment"],
        "enx": ["SPICE soot smoke point", "PSI-107 overview"],
        "pt": ["O que foi o SPICE?", "Fale sobre o experimento SPICE"]}),
    "daft": (["experiment_overview"], ["table"], {
        "en": ["What was DAFT?", "Tell me about the Dust and Aerosol Measurement Feasibility Test"],
        "enx": ["DAFT dust aerosol ISS", "PSI-47 summary"],
        "pt": ["O que foi o DAFT?", "Fale sobre o experimento DAFT"]}),
    "flex2": (["experiment_overview"], ["table"], {
        "en": ["What was FLEX-2?", "Tell me about FLEX-2"],
        "enx": ["flex 2 fuels and conditions", "PSI-68 overview"],
        "pt": ["O que foi o FLEX-2?", "Fale sobre o FLEX-2"]}),
    "o2_whatif_value": (["assess_atmosphere"], ["chart"], {
        "en": ["What changes if O2 goes to 30% at 101 kPa?", "What if we use 101 kPa and 30% oxygen?"],
        "enx": ["oxygen raised to 30 percent at 1 atm", "101 kPa, 30% O2 - covered?"],
        "pt": ["O que muda se o O2 for para 30% a 101 kPa?", "E se usarmos 101 kPa e 30% de oxigênio?"]}),
}

SYSTEM_OPENERS = [
    ("lunar_habitat", "I'm designing a lunar habitat. What are the main fire safety factors?"),
    ("lunar_habitat", "Estou projetando uma base lunar. Quais os principais riscos de incêndio?"),
    ("mars_habitat", "We are planning a Mars habitat. Review fire safety for me."),
    ("space_station", "Review fire safety for a new space station module."),
    ("pressurized_rover", "We are building a pressurized rover for the Moon. Fire risks?"),
]
ATMOS = [("8.2 psi and 34% oxygen", 56.54, 34.0), ("70 kPa and 26.5% oxygen", 70.0, 26.5), ("101 kPa and 21% oxygen", 101.0, 21.0)]
FOLLOWUPS = [
    [("Explain that chart in simpler terms.", [], []), ("Can you export the data behind that graph?", ["export_data"], ["downloads"])],
    [("What is the strongest uncertainty in your recommendation?", [], []), ("Which findings are based on actual measurements?", [], [])],
    [("Can we compare silicone and PMMA?", ["materials_evidence"], ["table"]), ("What happens if the ventilation system fails?", ["compare_ventilation_designs"], ["chart"])],
]


def multi_turn() -> list[dict]:
    convs = []
    for si, (system, opener) in enumerate(SYSTEM_OPENERS):
        for ai, (atm, p, o2) in enumerate(ATMOS):
            for fi, fus in enumerate(FOLLOWUPS):
                turns = [{"text": opener, "tools": ["fire_safety_factors"], "blocks": ["matrix"]},
                         {"text": f"We plan {atm}. Now change the atmosphere and compare the results.",
                          "tools": ["assess_atmosphere"], "blocks": ["chart"], "project": {"system": system, "pressure_kPa": p, "o2_pct": o2}}]
                for text, tools, blocks in fus:
                    turns.append({"text": text, "tools": tools, "blocks": blocks, "project": {"system": system, "o2_pct": o2}})
                convs.append({"id": f"mt-{si}-{ai}-{fi}", "turns": turns})
    return convs


HOLDOUT = [
    ("I need to pick wall panels for a lunar lander cabin at 34% oxygen; what evidence exists?", ["fire_safety_factors", "assess_atmosphere", "materials_evidence", "search_evidence"]),
    ("Is NASA-STD-6001 upward flammability testing conservative for microgravity?", ["search_evidence", "materials_evidence", "get_evidence"]),
    ("If a methanol leak forms 4 mm droplets, how long would they burn?", ["droplet_burn_time"]),
    ("Plot how much oxygen is available at 56.5 kPa and 34% compared with the ISS", ["assess_atmosphere"]),
    ("Our station uses 0.2 m/s cabin airflow - does that make flames spread faster?", ["search_evidence", "saffire2_flow_case_study", "compare_ventilation_designs", "fire_safety_factors"]),
    ("Which NASA experiment burned the largest sample ever in space?", ["search_evidence", "experiment_overview"]),
    ("Could a fire on Mars spread faster than on the Moon?", ["compare_gravity_regimes", "fire_safety_factors"]),
    ("Show me the measured diameter curve for the heptane droplet that kept vaporizing", ["flex035_case_study"]),
    ("Is there any battery thermal runaway data in your database?", ["fire_safety_factors", "search_evidence"]),
    ("How many combustion investigations are in PSI and how big is the archive?", ["search_evidence", "evidence_coverage_matrix"]),
    ("What would happen to the burning rate if we replaced nitrogen with helium?", ["chart_flex_burning_rate_vs_oxygen", "get_evidence", "search_evidence"]),
    ("Faça uma tabela comparando Kapton e Teflon", ["materials_evidence"]),
    ("Qual atmosfera é mais segura: 66.2 kPa com 28.5% ou 56.5 kPa com 34%?", ["assess_atmosphere"]),
    ("Quais experimentos usaram fumaça e detectores?", ["smoke_particle_sizes", "search_evidence", "experiment_overview"]),
    ("Explique por que a gravidade lunar não pode ser interpolada", ["compare_gravity_regimes", "get_evidence", "search_evidence"]),
    ("airlock dust and smoke detectors false alarms?", ["smoke_particle_sizes", "search_evidence"]),
    ("Give me a decision matrix for a crew capsule", ["fire_safety_factors"]),
    ("Does the PSI FLEX table have any errors?", ["experiment_overview", "flex_query", "search_evidence"]),
    ("What did BASS-II do with nitrogen?", ["experiment_overview", "search_evidence"]),
    ("How long until smoke from a battery bay reaches the crew module?", ["compare_ventilation_designs", "fire_safety_factors"]),
    ("Convert 10.2 psi to kPa", ["convert_units", "assess_atmosphere", "search_evidence"]),
    ("I'm using Nomex and PMMA in a Mars habitat at 70 kPa and 26.5% O2 - review it", ["fire_safety_factors", "materials_evidence", "assess_atmosphere"]),
    ("Did any silicone sample burn in Saffire-II?", ["materials_evidence", "saffire2_flow_case_study", "experiment_overview"]),
    ("What's the evidence for cool flames at high pressure?", ["flex035_case_study", "search_evidence", "experiment_overview"]),
    ("Which is riskier, pure oxygen at 34 kPa or air at 101 kPa?", ["assess_atmosphere", "search_evidence", "chart_flex_burning_rate_vs_oxygen"]),
    ("Summarize the lessons of Apollo 13 for oxygen tanks on a lunar base", ["search_evidence", "fire_safety_factors"]),
    ("Graph smoke particle size versus material", ["smoke_particle_sizes"]),
    ("What experiments support suppression design?", ["evidence_coverage_matrix", "search_evidence", "chart_flex_burning_rate_vs_oxygen", "get_evidence"]),
    ("Is the ISS cabin atmosphere covered by solid-material tests?", ["assess_atmosphere", "search_evidence", "evidence_coverage_matrix"]),
    ("Which of your findings has the biggest uncertainty?", ["search_evidence", "get_evidence"]),
]


def single_turn() -> list[dict]:
    out = []
    for topic, (tools, blocks, styles) in TOPICS.items():
        for style, phrasings in styles.items():
            for i, q in enumerate(phrasings):
                out.append({"id": f"{topic}-{style}-{i}", "family": f"{topic}:{style}", "topic": topic, "style": style,
                            "text": q, "tools": tools, "blocks": blocks})
    return out
