"""The Verified link: a frozen copy of an approved case study that anyone can check.

On publish we save exactly what was approved — the sentences, the facts and quotes behind each one,
who approved it and the approval fingerprint — under a random token. The public page reads only that
copy, recomputes the fingerprint from it and shows the evidence for every sentence. Later edits to
the project never change a published copy; the page only notes that a newer version exists.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets

from .models import SECTION_TITLES, ProjectRecord, now
from .review import can_export

EVIDENCE = ("full", "masked", "labels")  # quotes · quotes with unrelated details hidden · check results only
MASK = "███"  # ███
LABEL_TEXT = {"supported": "Stated in the notes", "reworded": "Same meaning as the notes"}

# a token that may give away something confidential: numbers and money, emails, links, Capitalised words
_SENSITIVE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.]+"                      # email
    r"|https?://\S+|www\.\S+"                       # link
    r"|[$€£₩¥]?\d[\d,.:/]*(?:%|[kKmMbB]\b)?"        # numbers, money, dates
    r"|\b[A-Z][\w&'-]*"                             # names (any capitalised word)
)


class VerifyError(ValueError):
    pass


def new_token() -> str:
    return secrets.token_urlsafe(8).replace("-", "x").replace("_", "y")[:10]


def _words(text: str) -> set[str]:
    return {w.lower().strip(".,") for w in re.findall(r"[\w$€£₩¥%.,:/@&'-]+", text)}


def mask_quote(quote: str, sentence: str, client: str = "") -> str:
    """Hide details in the quote that the published sentence doesn't already say.

    What the sentence says stays readable — that is the evidence; anything else that looks like a name,
    number, email or link becomes ███, and so does the client's name when it is hidden."""
    keep = _words(sentence)
    out = quote
    if client:
        out = re.sub(re.escape(client), MASK, out, flags=re.I)

    def repl(m: re.Match) -> str:
        tok = m.group(0)
        if tok == MASK or tok.lower().strip(".,") in keep:
            return tok
        if m.start() == 0 or re.search(r"[.!?:\n]\s*$", out[:m.start()]):  # a sentence's first word
            if not any(ch.isdigit() for ch in tok) and "@" not in tok and "://" not in tok:
                return tok
        return MASK

    out = _SENSITIVE.sub(repl, out)
    return re.sub(rf"(?:{MASK}[\s,]*){{2,}}", MASK + " ", out).strip()


def fingerprint(payload: dict) -> str:
    """Same recipe as ProjectRecord.content_hash, so the copy can be checked against the approval."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def snapshot(record: ProjectRecord, evidence: str = "full", show_client: bool = True) -> dict:
    """The frozen copy published under a token. Raises unless the project is approved and unchanged."""
    if not can_export(record):
        raise VerifyError("Approve the case study first. Only an approved, unchanged case study can be published.")
    if show_client and record.client_signoff.get("decision") == "anonymous" and record.input.client_name.strip():
        raise VerifyError("The client asked to stay anonymous. Publish with the client's name hidden.")
    if evidence not in EVIDENCE:
        raise VerifyError(f"Evidence must be one of {', '.join(EVIDENCE)}.")
    facts = {f.id: f for f in record.facts}
    client = record.input.client_name.strip()
    hidden = "" if show_client else client
    sections, sources = [], set()
    for key, title in SECTION_TITLES.items():
        rows = []
        for c in record.active_claims(key):
            used = [facts[i] for i in c.fact_ids if i in facts]
            ev = []
            for f in used:
                if f.source_ref:
                    sources.add(f.source_ref.split(",")[0].strip())
                if evidence == "labels":
                    continue
                quote = f.quote if evidence == "full" else mask_quote(f.quote, c.text, hidden)
                ev.append({"quote": quote, "source": f.source_ref if evidence == "full" else ""})
            text = c.text if show_client or not client else re.sub(re.escape(client), "the client", c.text, flags=re.I)
            rows.append({"id": c.id, "text": text, "label": (c.label.value if c.label else "supported"),
                         "estimate": any(f.estimate for f in used), "n_facts": len(used), "evidence": ev,
                         "manual": c.manual, "client_confirmed": bool(c.client_confirmed)})
        if rows:
            sections.append({"key": key, "title": title, "sentences": rows})
    return {
        "v": 1,
        "project_id": record.id,
        "title": record.input.title or "Untitled project",
        "client": client if show_client else "",
        "evidence": evidence,
        "approved_by": record.approved_by,
        "approved_at": record.approved_at,
        "published_at": now(),
        "hash": record.approved_hash,
        "n_sources": len(sources),
        "sections": sections,
        "client_signoff": ({"by": record.client_signoff.get("by", ""), "on": record.client_signoff.get("on", "")}
                           if record.client_signoff and any(c.client_confirmed for c in record.active_claims()) else {}),
        # exactly what the approval fingerprint covers: kept so the page can recompute it
        "signed": {
            "title": record.input.title,
            "client": record.input.client_name,
            "claims": [(c.id, c.section, c.text) for c in record.active_claims()],
            "images": [i.model_dump() for i in record.input.images],
        },
    }


def intact(copy: dict) -> bool:
    """True when the stored copy still matches the fingerprint the reviewer approved."""
    signed = copy.get("signed") or {}
    claims = [list(c) for c in signed.get("claims", [])]
    if fingerprint({**signed, "claims": claims}) != copy.get("hash"):
        return False
    shown = {s["id"]: s["text"] for sec in copy.get("sections", []) for s in sec["sentences"]}
    approved = {c[0]: c[2] for c in claims}
    if set(shown) != set(approved):
        return False
    client = signed.get("client") or ""
    for cid, text in shown.items():  # what is shown is what was approved (client name may be swapped out)
        if text != approved[cid] and not (client and not copy.get("client")
                                          and re.sub(re.escape(client), "the client", approved[cid], flags=re.I) == text):
            return False
    return True


def public_view(copy: dict, live_hash: str | None) -> dict:
    """What the public page shows. Never includes the fingerprint input or the project id."""
    ok = intact(copy)
    return {
        "title": copy["title"],
        "client": copy["client"],
        "evidence": copy["evidence"],
        "approved_by": copy["approved_by"],
        "approved_on": copy["approved_at"][:10],
        "published_on": copy["published_at"][:10],
        "hash_short": copy["hash"][:12],
        "intact": ok,
        "newer_version": ok and live_hash is not None and live_hash != copy["hash"],
        "n_sentences": sum(len(s["sentences"]) for s in copy["sections"]),
        "n_sources": copy.get("n_sources", 0),
        "signoff": copy.get("client_signoff") or {},
        "n_confirmed": sum(1 for s in copy["sections"] for x in s["sentences"] if x.get("client_confirmed")),
        "sections": [{"key": s["key"], "title": s["title"],
                      "sentences": [{**x, "label_text": LABEL_TEXT.get(x["label"], x["label"])} for x in s["sentences"]]}
                     for s in copy["sections"]],
    }
