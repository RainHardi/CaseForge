"""Document renderers. Each one refuses to produce a final document unless the project is approved."""

from __future__ import annotations

from ..models import ProjectRecord
from ..review import can_export


class ExportBlocked(PermissionError):
    pass


def require_approved(record: ProjectRecord, draft: bool) -> None:
    """draft=True allows a watermarked preview for reviewers; final output needs approval."""
    if draft:
        return
    if not can_export(record):
        raise ExportBlocked(
            "Export blocked: this project is not approved, or it was changed after approval. "
            "Review it and approve it first."
        )


BRAND = {
    "name": "CaseForge",
    "ink": "#1B2A41",
    "accent": "#E8A317",
    "muted": "#5B6675",
    "soft": "#F4F1EA",
    "line": "#D9D4C7",
}
