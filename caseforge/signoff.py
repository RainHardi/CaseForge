"""Client sign-off: the client confirms the numbers, quotes and mentions of them through one link.

The team sends a link after approval. The client sees only what needs their word and answers each
item: confirm, suggest a fix, or remove; then says whether their name may be published. Confirmations
mark the sentences (the approval stays: the text didn't change). Fixes and removals come back to the
team as suggestions; using one edits the case study, so it is re-checked and needs approval again.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from .models import ProjectRecord, now
from .review import ReviewError, add_to_source, can_export, delete_claim, edit_claim

DAYS = 14
ACTIONS = ("confirm", "fix", "remove")
DECISIONS = ("named", "anonymous")
_NUMBER = re.compile(r"\d")
_QUOTE = re.compile(r"[\"“”]")


class SignoffError(ValueError):
    pass


def new_token() -> str:
    return secrets.token_urlsafe(12).replace("-", "x").replace("_", "y")[:16]


def needs_client(record: ProjectRecord, text: str, section: str) -> bool:
    client = record.input.client_name.strip().lower()
    return bool(section == "results" or _NUMBER.search(text) or _QUOTE.search(text)
                or (client and client in text.lower()))


def items(record: ProjectRecord) -> list[dict]:
    """The sentences the client is asked about, in reading order."""
    return [{"id": c.id, "section": c.section, "text": c.text}
            for c in record.active_claims() if needs_client(record, c.text, c.section)]


def request(record: ProjectRecord, contact: str = "") -> dict:
    """A new sign-off request (stored by the caller under its token)."""
    if not can_export(record):
        raise SignoffError("Approve the case study first, then ask the client to confirm it.")
    asked = items(record)
    if not asked:
        raise SignoffError("Nothing here needs the client's word: no numbers, quotes or mentions of them.")
    created = datetime.now(timezone.utc)
    return {"project_id": record.id, "title": record.input.title or "Untitled project",
            "client": record.input.client_name, "contact": contact.strip()[:120], "hash": record.approved_hash,
            "items": asked, "created_at": created.isoformat(timespec="seconds"),
            "expires_at": (created + timedelta(days=DAYS)).isoformat(timespec="seconds"),
            "answers": {}, "decision": "", "signed_by": "", "submitted_at": ""}


def state(req: dict, live_hash: str | None) -> str:
    """open · answered · expired · changed (the case study changed since the link was sent)."""
    if req.get("submitted_at"):
        return "answered"
    if datetime.fromisoformat(req["expires_at"]) < datetime.now(timezone.utc):
        return "expired"
    if live_hash != req["hash"]:
        return "changed"
    return "open"


def submit(req: dict, answers: dict, decision: str, signed_by: str) -> dict:
    """Validates the client's answers and returns the updated request."""
    signed_by = " ".join((signed_by or "").split())[:120]
    if not signed_by:
        raise SignoffError("Type your name so the team knows who confirmed it.")
    if decision not in DECISIONS:
        raise SignoffError("Choose whether your company's name may be published.")
    clean = {}
    for it in req["items"]:
        a = answers.get(it["id"]) or {}
        action = a.get("action")
        if action not in ACTIONS:
            raise SignoffError("Answer every item: confirm it, suggest a fix, or remove it.")
        text = " ".join(str(a.get("text") or "").split())[:600]
        if action == "fix" and (not text or text == it["text"]):
            raise SignoffError("For a suggested fix, change the sentence to what it should say.")
        clean[it["id"]] = {"action": action, "text": text if action == "fix" else ""}
    return {**req, "answers": clean, "decision": decision, "signed_by": signed_by, "submitted_at": now()}


def apply_answers(record: ProjectRecord, req: dict) -> int:
    """Marks the confirmed sentences on the project (only if it is still the version the client saw).

    Returns how many sentences were marked. The approval stays: no text changes here."""
    if record.approved_hash != req["hash"]:
        return 0
    marked = 0
    on = req["submitted_at"][:10]
    for c in record.active_claims():
        a = req["answers"].get(c.id)
        if a and a["action"] == "confirm" and c.text == next(i["text"] for i in req["items"] if i["id"] == c.id):
            c.client_confirmed = on
            marked += 1
    record.client_signoff = {"by": req["signed_by"], "company": req.get("client", ""), "on": on,
                             "decision": req["decision"]}
    fixes = sum(1 for a in req["answers"].values() if a["action"] != "confirm")
    record.log("client sign-off", f"{req['signed_by']}: {marked} confirmed, {fixes} to look at, "
                                  f"name {'may be published' if req['decision'] == 'named' else 'must be hidden'}")
    return marked


def use_suggestion(record: ProjectRecord, req: dict, claim_id: str, llm, by: str) -> None:
    """The team accepts the client's fix or removal for one sentence."""
    a = req.get("answers", {}).get(claim_id)
    if not a or a["action"] == "confirm":
        raise ReviewError("The client confirmed this sentence; there is nothing to apply.")
    if a["action"] == "remove":
        delete_claim(record, claim_id, by)
        record.log("client removal applied", f"{claim_id} (asked by {req['signed_by']})", by)
        return
    # the client's correction becomes part of the source, so the new wording can be checked against it
    add_to_source(record, f"Correction confirmed by the client ({req['signed_by']}, {req['submitted_at'][:10]}): "
                          f"{a['text']}", llm, by=by)
    edit_claim(record, claim_id, a["text"], llm, by)
    record.claim(claim_id).client_confirmed = req["submitted_at"][:10]
    record.log("client fix applied", f"{claim_id} (from {req['signed_by']})", by)
