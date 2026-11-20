"""Proof library: search every approved case study in a workspace and build a proof sheet for a prospect.

A salesperson types who they are pitching ("logistics company, wants lower costs, uses Postgres").
CaseForge ranks the approved case studies and their sentences, and builds a one-page proof sheet from
them. Every sentence on the sheet is copied word for word from an approved case study, so nothing
new is written and nothing needs checking again. Clients who asked to stay anonymous stay anonymous.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .anonymize import apply as swap_names
from .models import SECTION_TITLES, ProjectRecord
from .review import can_export

MAX_PROJECTS = 10
SHEET_PROJECTS = 3
SHEET_SENTENCES = 4  # per case study, plus its best result
_STOP = set("""a an and are as at be but by for from has have i in into is it its of on or our so that the their
them they this to was we were what when which who will with you your company client clients team project wants want
need needs looking someone something like using use uses used""".split())
SYNONYMS = {  # a small push towards what people mean, not just what they type
    "cost": ["saving", "budget", "cheaper", "spend", "expense", "fuel", "price", "money"], "saving": ["cost"],
    "cheap": ["cost"], "lower": ["reduce", "cut", "down", "fell", "less", "drop", "saving"], "reduce": ["lower", "cut", "down", "fell"],
    "increase": ["more", "higher", "grow", "rose", "up"], "more": ["increase", "higher", "grow"], "grow": ["increase", "rose"],
    "fast": ["faster", "speed", "time", "quick", "hour", "minute"], "slow": ["time", "delay", "hour"],
    "time": ["hour", "minute", "day", "faster"], "logistic": ["shipping", "freight", "delivery", "warehouse", "dispatch"],
    "shipping": ["logistic", "freight", "delivery"], "clinic": ["dental", "patient", "health", "hospital", "appointment"],
    "health": ["clinic", "patient", "hospital"], "retail": ["shop", "store", "inventory", "stock"],
    "inventory": ["stock", "warehouse"], "dashboard": ["report", "reporting", "chart"], "report": ["dashboard"],
    "automation": ["automate", "manual", "script"], "manual": ["automate", "spreadsheet", "excel"],
    "spreadsheet": ["excel", "manual"], "error": ["mistake", "accuracy", "duplicate"], "ai": ["model", "predict", "ml"],
    "ml": ["model", "predict", "ai"], "predict": ["model", "forecast"], "mobile": ["app", "android", "ios"],
    "app": ["mobile", "portal", "web"], "booking": ["appointment", "schedule", "portal"],
}


def _stem(w: str) -> str:
    for suf in ("ies", "ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z][a-z0-9+#.-]*[a-z0-9+#]|[a-z]", text.lower()) if w not in _STOP]


def _query_terms(query: str) -> dict[str, float]:
    terms: dict[str, float] = {}
    for t in tokens(query):
        terms[t] = max(terms.get(t, 0), 1.0)
        for s in SYNONYMS.get(t, []):
            terms[_stem(s)] = max(terms.get(_stem(s), 0), 0.5)
    return terms


def approved(records: list[ProjectRecord]) -> list[ProjectRecord]:
    return [r for r in records if can_export(r)]


def _is_metric(text: str, section: str) -> bool:
    return section in ("results", "summary") and bool(re.search(r"\d", text))


def search(records: list[ProjectRecord], query: str) -> list[dict]:
    """Approved case studies ranked for the query, each with its best-matching sentences (BM25)."""
    recs = approved(records)
    docs = [(r, c, tokens(c.text + " " + (r.input.title if c.section == "summary" else ""))) for r in recs
            for c in r.active_claims()]
    terms = _query_terms(query)
    if not docs:
        return []
    n = len(docs)
    avg = sum(len(d[2]) for d in docs) / n or 1
    df = Counter(t for _, _, toks in docs for t in set(toks))
    scored: dict[str, list[tuple[float, object]]] = {}
    for r, c, toks in docs:
        tf = Counter(toks)
        s = 0.0
        for t, w in terms.items():
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += w * idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(toks) / avg))
        if s > 0 and _is_metric(c.text, c.section):
            s *= 1.6  # a result with a number is the proof people want
        elif s > 0 and c.section in ("results", "client_problem", "work_done"):
            s *= 1.2  # the problem, the solution and the outcome read best on a sheet
        scored.setdefault(r.id, []).append((s, c))
    out = []
    for r in recs:
        rows = sorted(scored.get(r.id, []), key=lambda x: -x[0])
        hits = [(s, c) for s, c in rows if s > 0]
        title_hit = sum(w for t, w in terms.items() if t in tokens(r.input.title))
        score = sum(s for s, _ in hits[:3]) + 0.8 * title_hit
        if terms and score <= 0:
            continue
        metrics = [c for c in r.active_claims() if _is_metric(c.text, c.section)]
        out.append({
            "id": r.id, "title": r.input.title or "Untitled project", "client": r.input.client_name,
            "anonymous": r.client_signoff.get("decision") == "anonymous", "approved_by": r.approved_by,
            "approved_on": r.approved_at[:10], "score": round(score, 3),
            "tools": [c.text for c in r.active_claims("tools")][:2],
            "matches": [{"id": c.id, "text": c.text, "section": c.section, "metric": _is_metric(c.text, c.section)}
                        for _, c in hits[:SHEET_SENTENCES + 2]],
            "metrics": [{"id": c.id, "text": c.text} for c in metrics[:3]],
            "n_sentences": len(r.active_claims()),
        })
    out.sort(key=lambda x: (-x["score"], x["title"]))
    return out[:MAX_PROJECTS]


def _display(r: ProjectRecord, anonymize_all: bool):
    """(text transform, client label) — anonymous clients are never named on a sheet."""
    hide = anonymize_all or r.client_signoff.get("decision") == "anonymous"
    client = r.input.client_name.strip()
    if not hide:
        return (lambda t: t), client
    if r.anon_map:
        return (lambda t: swap_names(t, r.anon_map)), ""
    return (lambda t: re.sub(re.escape(client), "the client", t, flags=re.I) if client else t), ""


def sheet(records: list[ProjectRecord], query: str, picks: dict[str, list[str]] | None = None,
          anonymize_all: bool = False, links: dict[str, str] | None = None) -> dict:
    """The proof sheet. picks = {project_id: [claim ids]}; without picks the best matches are used."""
    by_id = {r.id: r for r in approved(records)}
    if not picks:
        picks = {}
        hits = search(records, query)
        top = hits[0]["score"] if hits else 0
        for hit in [h for h in hits if not query.strip() or h["score"] >= 0.35 * top][:SHEET_PROJECTS]:
            ids = [m["id"] for m in hit["matches"][:SHEET_SENTENCES]]
            best_metric = next((m["id"] for m in hit["metrics"] if m["id"] not in ids), None)
            picks[hit["id"]] = ids + ([best_metric] if best_metric else [])
    blocks = []
    for pid, ids in picks.items():
        r = by_id.get(pid)
        if not r or not ids:
            continue
        tx, client = _display(r, anonymize_all)
        claims = {c.id: c for c in r.active_claims()}
        order = [c.id for c in r.active_claims()]
        chosen = sorted({i for i in ids if i in claims}, key=order.index)  # reading order, approved sentences only
        if not chosen:
            continue
        blocks.append({
            "id": pid, "title": tx(r.input.title or "Untitled project"), "client": client,
            "approved_by": r.approved_by, "approved_on": r.approved_at[:10],
            "verified_url": (links or {}).get(pid, ""),
            "sentences": [{"text": tx(claims[i].text), "section": SECTION_TITLES.get(claims[i].section, ""),
                           "metric": _is_metric(claims[i].text, claims[i].section),
                           "confirmed": bool(claims[i].client_confirmed)} for i in chosen],
        })
    return {"query": " ".join(query.split())[:200], "projects": blocks,
            "n_sentences": sum(len(b["sentences"]) for b in blocks)}


def sheet_text(s: dict) -> str:
    lines = [f"Relevant work: {s['query']}" if s["query"] else "Relevant work", ""]
    for b in s["projects"]:
        lines.append(b["title"] + (f" ({b['client']})" if b["client"] else ""))
        lines += [f"- {x['text']}" for x in b["sentences"]]
        if b["verified_url"]:
            lines.append(f"  Check every sentence: {b['verified_url']}")
        lines.append("")
    lines.append("Every sentence is quoted from an approved, fact-checked case study (CaseForge).")
    return "\n".join(lines).strip()
