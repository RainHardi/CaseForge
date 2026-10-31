"""Settings, read from environment variables (and a local .env file if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is optional; plain env vars work without it
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    data_dir: Path
    # "auto"    -> Gemini if a key is set, otherwise offline rules
    # "gemini"  -> always Gemini (error if no key)
    # "offline" -> never call an LLM (deterministic, free, good for tests)
    llm_mode: str

    @property
    def use_gemini(self) -> bool:
        if self.llm_mode == "offline":
            return False
        if self.llm_mode == "gemini":
            return True
        return bool(self.gemini_api_key)


def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        # Pin a concrete model in .env for the final tests (Question Log Q-015).
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip(),
        data_dir=Path(os.getenv("CASEFORGE_DATA_DIR", str(ROOT / "data" / "projects"))),
        llm_mode=os.getenv("CASEFORGE_LLM_MODE", "auto").strip().lower(),
    )
