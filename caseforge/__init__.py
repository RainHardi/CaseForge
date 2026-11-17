"""CaseForge — turns messy project notes into faithful, approved case studies.

Pipeline:  input -> fact extraction -> writing -> faithfulness check -> human review -> export
"""

__version__ = "0.1.0"

from .models import _resolve_forward_refs  # noqa: E402

_resolve_forward_refs()
