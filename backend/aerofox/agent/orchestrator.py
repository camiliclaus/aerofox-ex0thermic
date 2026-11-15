"""One conversational turn: understand -> update state -> plan/LLM -> verify -> structured response."""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import date

from ..config import settings
from ..evidence.store import get_store
from . import llm
from .nlu import explicit_language, fold, understand
from .planner import T, compose, make_plan
from .state import ProjectState, Session, SessionStore
from .tools import run_tool

log = logging.getLogger("aerofox.turn")
SESSIONS = SessionStore(settings.max_sessions, settings.session_ttl_s)


class Budget:
    """Daily cap on language-model turns to protect the public demo from runaway cost."""

    def __init__(self, limit: int):
        self.limit, self.day, self.used = limit, date.today(), 0
        self._l = threading.Lock()

    def take(self) -> bool:
        with self._l:
            if date.today() != self.day:
                self.day, self.used = date.today(), 0
            if self.used >= self.limit:
                return False
            self.used += 1
            return True


BUDGET = Budget(settings.llm_daily_turn_budget)
CITE = re.compile(r"\[([A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)*)\]")


def _apply_understanding(s: Session, u) -> dict:
    """Write only explicitly stated facts into the project state."""
    changes = {}
    data = s.project.model_dump()
    if (not u.system and len(u.text.split()) <= 6 and u.gravity in ("lunar", "mars")
            and data.get("system") in ("lunar_habitat", "mars_habitat")
            and s.last_topic == "fire_safety_factors"):
        u.system = {"lunar": "lunar_habitat", "mars": "mars_habitat"}[u.gravity]
    if u.system and u.system != data.get("system"):
        changes["system"] = u.system
    if u.gravity and len(set(u.gravities)) <= 1 and ("design_review" in u.intents or u.system or "what_if" in u.intents):
        if u.gravity != data.get("gravity"):
            changes["gravity"] = u.gravity
    written = fold(u.text)
    temporary = bool(re.search(r"\b(?:what if|what happens if|suppose|hypothetical|e se|suponha|hipotetic\w*)\b", written))
    reported = bool(u.experiments)
    negated = bool(re.search(r"\b(?:do not assume|don.t assume|nao assuma|nao presuma)\b", written))
    if not (temporary or reported or negated) and u.pressure_kPa is not None:
        changes["pressure_kPa"] = u.pressure_kPa
    if not (temporary or reported or negated) and u.o2_pct is not None:
        changes["o2_pct"] = u.o2_pct
    if u.materials and ("design_review" in u.intents or "my" in u.text.lower() or "meu" in u.text.lower() or "using" in u.text.lower()):
        changes["materials"] = list(dict.fromkeys(data["materials"] + u.materials))
    if changes:
        data.update(changes)
        try:
            s.project = ProjectState(**data)
        except Exception:
            changes = {"rejected": "values outside physical limits were ignored"}
    return changes


def _finalise_blocks(s: Session, results: list[dict]) -> list[dict]:
    blocks = []
    for r in results:
        if not r.get("ok"):
            continue
        for b in r.get("blocks", []):
            if "artifact_id" not in b and b.get("type") != "downloads":
                s.add_artifact(b)
            if b.get("artifact_id") and b["type"] in ("chart", "table", "matrix"):
                b["csv_url"] = f"/api/sessions/{s.id}/artifacts/{b['artifact_id']}.csv"
            if b.get("artifact_id") and b["type"] == "flowchart":
                b["mermaid_url"] = f"/api/sessions/{s.id}/artifacts/{b['artifact_id']}.mmd"
            blocks.append(b)
    return blocks


def handle_turn(session_id: str | None, text: str, request_id: str) -> dict:
    t0 = time.monotonic()
    s = SESSIONS.get_or_create(session_id)
    with SESSIONS.lock(s.id):
        text = (text or "").strip()
        if not text:
            return {"error": "empty message", "session_id": s.id}
        text = text[: settings.max_message_chars]
        u = understand(text)
        if language := explicit_language(text):
            s.preferred_language = language
        s.language = s.preferred_language or (s.language if u.refers_back and len(text.split()) < 4 else u.language)
        changes = _apply_understanding(s, u)
        mode, notice, results, usage, model = "offline", None, [], None, None
        answer = ""
        removed = 0
        generation = {"status": "evidence_only", "reason": "disabled", "recovery": []}
        tool_results_available = False
        if llm.available():
            if BUDGET.take():
                try:
                    draft = s.model_copy(update={"artifacts": dict(s.artifacts)})
                    out = llm.run_turn(draft, text, u, deadline=t0 + settings.turn_deadline_s)
                    s.artifacts, s.artifact_sequence = draft.artifacts, draft.artifact_sequence
                    answer, results, usage, model, mode = out["text"], out["results"], out["usage"], out["model"], "llm"
                    removed = out["removed"]
                    generation = out["generation"]
                    tool_results_available = True
                    if generation["status"] == "evidence_only":
                        mode, model = "offline", None
                        notice = ("O modelo não concluiu a resposta. A análise já calculada foi preservada."
                                  if s.language == "pt" else "The model could not finish its explanation. The verified analysis is shown below.")
                except llm.LLMUnavailable as e:
                    generation["reason"] = e.code
                    if e.code == "busy":
                        notice = ("O modelo local está ocupado. O motor offline respondeu a esta pergunta." if s.language == "pt"
                                  else "The local model is busy. The offline engine answered this turn.")
                    elif e.code in {"timeout", "deadline"}:
                        notice = ("O modelo local excedeu o tempo de resposta. O motor offline respondeu a esta pergunta." if s.language == "pt"
                                  else "The local model exceeded its time limit. The offline engine answered this turn.")
                    else:
                        notice = ("O modelo local está indisponível. A resposta usa o motor offline."
                                  if s.language == "pt" else "The local model is unavailable. The offline engine answered this turn.")
                    log.warning("rid=%s llm fallback: %s", request_id, e)
                except Exception:  # contain model or protocol bugs without logging project inputs
                    generation["reason"] = "internal"
                    notice = ("O motor offline respondeu após um erro no modelo local." if s.language == "pt"
                              else "The offline engine answered after an inference error.")
                    log.error("rid=%s unexpected local inference error", request_id)
            else:
                notice = "Daily language-model budget reached; answered with the offline engine."
                generation["reason"] = "budget"
        if mode == "offline" and not tool_results_available:
            plan = make_plan(u, s)
            results = [dict(run_tool(s, name, args), model_args=args) for name, args in plan.steps]
            answer = compose(u, s, plan, results)
            if plan.meta in ("simplify", "uncertainty", "evidence_status"):
                results = []
        blocks = _finalise_blocks(s, results)
        store = get_store()
        ev_ids: list[str] = []
        for r in results:
            if r.get("ok"):
                ev_ids += [e for e in r.get("evidence", []) if e not in ev_ids]
        cited = CITE.findall(answer)
        unknown = [c for c in cited if not store.get(c) and not c.startswith("FLEX")]
        for c in unknown:
            answer = answer.replace(f"[{c}]", "")
        for c in cited:
            if store.get(c) and c not in ev_ids:
                ev_ids.insert(0, c)
        cards = [store.get(e).card() for e in ev_ids if store.get(e)][:12]
        warnings = []
        for r in results:
            if r.get("ok"):
                warnings += [w for w in r.get("warnings", []) if w not in warnings]
        if unknown:
            warnings.append(f"Removed {len(unknown)} citation(s) that do not exist in the evidence store.")
        if removed:
            warnings.append(f"Removed {removed} citation(s) that were not returned by the tools.")
        topical = [r for r in results if r.get("ok") and r["tool"] not in ("search_evidence", "get_evidence", "export_data",
                                                                           "update_project", "convert_units")]
        if topical:
            last = topical[0]
            s.last_topic = last["tool"]
            s.last_args = {"_evidence": ev_ids, "_warnings": warnings,
                           "_tool_inputs": last.get("model_args", {})}
        elif ev_ids:
            s.last_args = {**s.last_args, "_evidence": ev_ids, "_warnings": warnings}
            s.last_topic = s.last_topic or "search_evidence"
        if blocks:
            s.last_blocks = [b["artifact_id"] for b in blocks if b.get("artifact_id")]
        s.remember("user", text)
        s.remember("assistant", answer)
        elapsed = round(time.monotonic() - t0, 3)
        log.info("rid=%s mode=%s status=%s reason=%s intents=%s tools=%s blocks=%d %.2fs", request_id, mode,
                 generation["status"], generation["reason"], sorted(u.intents), [r.get("tool") for r in results], len(blocks), elapsed)
        return {
            "session_id": s.id, "request_id": request_id, "mode": mode, "model": model, "notice": notice,
            "language": s.language, "answer": answer, "blocks": blocks, "evidence": cards, "warnings": warnings[:8],
            "verified_results": [
                {"tool": r["tool"], "text": r["summary"], "evidence": r.get("evidence", [])[:3]}
                for r in results if mode == "llm" and r.get("ok") and r.get("summary")
                and r["tool"] not in {"search_evidence", "get_evidence", "export_data"}
            ],
            "project": s.project.known(), "project_changes": changes,
            "understanding": {k: v for k, v in u.as_dict().items() if k in ("intents", "experiments", "system", "gravity",
                                                                           "pressure_kPa", "o2_pct", "materials")},
            "tools": [{"name": r.get("tool"), "ok": r.get("ok"), "elapsed_s": r.get("elapsed_s"), "error": r.get("error")} for r in results],
            "usage": usage, "generation": generation, "elapsed_s": elapsed,
            "offline_label": T[s.language]["offline"] if mode == "offline" else None,
        }
