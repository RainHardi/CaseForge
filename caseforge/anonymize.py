"""Anonymized version: the same approved case study with the client and people unnamed.

The team keeps a list of swaps ("Bright Smile Dental" → "a dental clinic", "Dana Lee" → "the clinic
manager"). An anonymized copy applies only those swaps to the approved text, so every number and
claim stays exactly as checked and approved. Swaps can't add numbers, and can't touch them.
"""

from __future__ import annotations

import re

from .models import ProjectRecord
from .review import ReviewError, can_export

MAX_SWAPS = 40
CLIENT_DEFAULT = "the client"
_STOP = {  # capitalised words that are not names
    "the", "a", "an", "we", "our", "they", "it", "this", "that", "these", "after", "before", "during", "over", "every",
    "each", "in", "on", "at", "for", "from", "with", "by", "to", "of", "and", "or", "but", "phase", "week", "month",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
    "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "q1", "q2", "q3", "q4",
    "api", "ui", "ux", "ai", "ml", "kpi", "mvp", "qa", "ci", "cd", "sql", "pdf", "csv", "excel", "slack", "jira",
}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_URL = re.compile(r"https?://\S+|www\.\S+")
_PHONE = re.compile(r"\+?\d[\d ()-]{7,}\d")
_NAME = re.compile(r"\b([A-Z][a-z]+(?:[- ](?:[A-Z][a-z]+|[A-Z]\.?)){1,3})\b")  # two to four Capitalised words


def client_descriptor(record: ProjectRecord) -> str:
    """A generic name for the client from the title: '… for a Dental Clinic' → 'a dental clinic'."""
    m = re.search(r"\bfor (an?|the) ([A-Za-z][\w -]{2,40})$", (record.input.title or "").strip())
    if m:
        return f"{m.group(1).lower()} {m.group(2).strip().lower()}"
    return CLIENT_DEFAULT


def _tech_words(record: ProjectRecord) -> set[str]:
    words = set()
    for c in record.active_claims("tools"):
        words |= {w.lower() for w in re.findall(r"[A-Za-z][\w.+#-]*", c.text)}
    for f in record.facts:
        if f.field == "tools":
            words |= {w.lower() for w in re.findall(r"[A-Za-z][\w.+#-]*", f.statement)}
    return words


def suggest(record: ProjectRecord) -> list[dict]:
    """Swaps worth making, found in the approved text: the client, people, emails, links, phones."""
    text = " ".join([record.input.title] + [c.text for c in record.active_claims()])
    out: list[dict] = []
    seen: set[str] = set()

    def add(term: str, replace: str, kind: str) -> None:
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            # the client, emails, links and phones are swapped by default; other names are only a hint
            out.append({"term": term, "replace": replace, "kind": kind, "on": kind != "name"})

    client = record.input.client_name.strip()
    if client:
        add(re.sub(r"\s*\((?:fictional|demo|sample)\)\s*$", "", client, flags=re.I), client_descriptor(record), "client")
        add(client, client_descriptor(record), "client")
    tech = _tech_words(record)
    title_words = {w.lower() for w in re.findall(r"[A-Za-z][\w-]*", record.input.title)}
    body = " ".join(c.text for c in record.active_claims())
    for m in _NAME.finditer(body):  # names: from the sentences only
        if all(p.lower() in title_words for p in re.split(r"[- ]", m.group(1))):
            continue  # words of the project title ("Appointment No-Show Prediction")
        name = m.group(1)
        parts = [p.lower().strip(".") for p in re.split(r"[- ]", name)]
        if any(p in _STOP or p in tech for p in parts) or name.lower() in seen:
            continue
        if any(name.lower() in s for s in seen):  # part of the client name
            continue
        before = body[:m.start()].rstrip()
        if (not before or before[-1] in ".!?:") and len(parts) < 3:  # "Supports Dutch …": a sentence start
            continue
        company = re.search(r"\b(group|inc|ltd|llc|gmbh|corp|logistics|freight|holdings|partners|bank|labs)$", name, re.I)
        add(name, "a partner company" if company else "", "name")
    for rx, rep, kind in ((_EMAIL, "[email]", "email"), (_URL, "[link]", "link"), (_PHONE, "[phone]", "phone")):
        for m in rx.finditer(text):
            add(m.group(0), rep, kind)
    return out[:MAX_SWAPS]


def clean(swaps: list) -> list[list[str]]:
    """Validated swaps as [[term, replacement], …]. A swap can never add, remove or change a number."""
    out, seen = [], set()
    for s in swaps or []:
        term, rep = (s.get("term"), s.get("replace")) if isinstance(s, dict) else (s[0], s[1])
        term, rep = " ".join(str(term or "").split()), " ".join(str(rep or "").split())
        if not term:
            continue
        if len(term) < 2 or len(term) > 120 or len(rep) > 120:
            raise ReviewError(f"“{term[:40]}”: names are 2 to 120 characters.")
        if re.search(r"\d", rep) or (re.search(r"\d", term) and not (_EMAIL.fullmatch(term) or _URL.fullmatch(term)
                                                                     or _PHONE.fullmatch(term))):
            raise ReviewError(f"“{term[:40]}” → “{rep[:40]}”: a swap can't change numbers. Only names are swapped.")
        if not rep:
            raise ReviewError(f"Write what to call “{term[:40]}” instead, or untick it.")
        if term.lower() in seen:
            continue
        seen.add(term.lower())
        out.append([term, rep])
    if len(out) > MAX_SWAPS:
        raise ReviewError(f"At most {MAX_SWAPS} swaps.")
    return out


def apply(text: str, swaps: list[list[str]]) -> str:
    """Longest name first, whole words only, any capitalisation; 'a dental clinic's' keeps the 's."""
    if not text or not swaps:
        return text
    for term, rep in sorted(swaps, key=lambda s: -len(s[0])):
        pat = re.compile(rf"(?<![\w@]){re.escape(term)}(?![\w@])", re.I)

        def sub(m: re.Match, rep=rep) -> str:
            start = m.start()
            sentence_start = start == 0 or re.search(r"[.!?]\s+$|^\s*$", text[:start]) is not None
            return rep[:1].upper() + rep[1:] if sentence_start and rep[:1].islower() else rep

        text = pat.sub(sub, text)
        if re.match(r"(?:an?|the) ", rep, re.I):  # "the Acme team" → "the a clinic team": drop the old article
            text = re.sub(rf"\b(?:[aA]n?|[tT]he) ({re.escape(rep)})",
                          lambda m: m.group(1)[:1].upper() + m.group(1)[1:] if m.group(0)[0].isupper() else m.group(1),
                          text)
        elif rep:  # fix the article in front of the swap only: "a Acme" → "an …", "an Uber" → "a …"
            vowel = rep[0].lower() in "aeiou"
            text = re.sub(rf"\b([aA])n? (?={re.escape(rep)})", lambda m, v=vowel: m.group(1) + ("n " if v else " "), text)
    return text


def leftovers(texts: list[str], swaps: list[list[str]]) -> list[str]:
    joined = " ".join(texts).lower()
    return [t for t, _ in swaps if re.search(rf"(?<![\w@]){re.escape(t.lower())}(?![\w@])", joined)]


def anonymized(record: ProjectRecord, swaps: list[list[str]] | None = None) -> ProjectRecord:
    """A copy of the approved project with the swaps applied, approved as the same reviewer.

    Only names change, so the copy carries the original approval; its fingerprint is recomputed
    for the anonymized text. The designed report comes along if it was approved."""
    swaps = swaps if swaps is not None else record.anon_map
    if not can_export(record):
        raise ReviewError("Approve the case study first.")
    if not swaps:
        raise ReviewError("Set up the name swaps first (Anonymized version).")
    from .report import report_ready  # here: report.py imports a lot

    report_ok = report_ready(record)
    rec = record.model_copy(deep=True)
    rec.input.title = apply(rec.input.title, swaps)
    rec.input.client_name = ""
    for c in rec.claims:
        c.text = apply(c.text, swaps)
    for f in rec.facts:
        f.statement, f.quote = apply(f.statement, swaps), apply(f.quote, swaps)
    for img in rec.input.images:
        img.caption = apply(img.caption, swaps)
    rec.approved_hash = rec.content_hash()
    if rec.report is not None:
        d = rec.report
        plan_json = d.plan.model_dump_json()
        for term, rep in sorted(swaps, key=lambda s: -len(s[0])):
            esc_term = term.replace("\\", "\\\\").replace('"', '\\"')
            plan_json = re.sub(rf"(?<![\w@]){re.escape(esc_term)}(?![\w@])", rep.replace("\\", "\\\\"), plan_json, flags=re.I)
        d.plan = type(d.plan).model_validate_json(plan_json)
        for e in d.elements:
            e.text = apply(e.text, swaps)
        if d.brand.company and leftovers([d.brand.company], swaps):
            d.brand.company = ""
        if record.input.logo and "brand" not in d.prefs.hide:  # a logo uploaded with the notes is the client's
            d.prefs.hide.append("brand")
        d.based_on_hash = rec.approved_hash
        d.approved_hash = d.design_hash() if report_ok else ""
    rec.anon_map = swaps
    return rec
