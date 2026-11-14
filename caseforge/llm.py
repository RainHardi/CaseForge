"""The only file that talks to an LLM. Swap providers here without touching the pipeline."""

from __future__ import annotations

import json
import os
import time
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class _Busy(LLMError):
    """The model is overloaded or rate-limited: worth trying another model."""


class LLM(Protocol):
    name: str
    calls: int

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T: ...


REQUEST_TIMEOUT_S = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "75"))  # one request
TOTAL_BUDGET_S = int(os.getenv("GEMINI_TOTAL_SECONDS", "150"))      # all retries + fallbacks for one call


class GeminiLLM:
    """Google Gemini via the official `google-genai` SDK, with JSON-schema output."""

    def __init__(self, api_key: str, model: str, max_attempts: int = 3, fallbacks: tuple[str, ...] = ()):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set. Put it in your .env file.")
        from google import genai  # imported lazily so offline mode needs no SDK

        from google.genai import types

        # without a timeout one stuck request can hold "Working on it…" for minutes
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_S * 1000))
        self.model = model
        self.name = f"gemini:{model}"
        self.max_attempts = max_attempts
        self.fallbacks = tuple(m for m in fallbacks if m and m != model)
        self.calls = 0
        self.budget_until = 0.0  # optional end time for a whole job (set by the pipeline)

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        """Asks the main model; when it stays busy ("503 high demand", rate limit) after its retries,
        the same request goes to the next model in GEMINI_FALLBACK_MODELS instead of failing."""
        last: LLMError | None = None
        self._deadline = time.monotonic() + TOTAL_BUDGET_S
        if self.budget_until:
            self._deadline = min(self._deadline, self.budget_until)
        for model in (self.model, *self.fallbacks):
            if time.monotonic() > self._deadline:
                break
            try:
                return self._ask(model, system, prompt, schema)
            except _Busy as e:
                last = LLMError(str(e))
        raise last or LLMError(f"Gemini didn't answer within {TOTAL_BUDGET_S}s. It's busy, try again in a minute.")

    def _ask(self, model: str, system: str, prompt: str, schema: type[T]) -> T:
        import httpx
        from google.genai import errors, types

        last_err: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self.calls += 1
                resp = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                if isinstance(resp.parsed, schema):
                    return resp.parsed
                return schema.model_validate_json(resp.text or "")
            except (httpx.TimeoutException, httpx.TransportError) as e:
                # slow or dropped connection: one more try at most, then the next model
                last_err = e
                if attempt >= 2 or time.monotonic() + REQUEST_TIMEOUT_S > self._deadline:
                    raise _Busy(f"Gemini took longer than {REQUEST_TIMEOUT_S}s ({type(e).__name__})") from e
                continue
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                # Badly shaped output: ask again. "Correct shape every time" is enforced here.
                last_err = e
            except errors.APIError as e:
                last_err = e
                if e.code in (429, 500, 502, 503, 504):
                    wait = min(10, 3 * 2 ** (attempt - 1))  # free-tier rate limits
                    if attempt < self.max_attempts and time.monotonic() + wait < self._deadline:
                        time.sleep(wait)
                        continue
                    raise _Busy(f"Gemini API error {e.code}: {e}") from e
                if e.code == 404 and model != self.model:
                    raise _Busy(f"fallback model {model!r} does not exist") from e
                raise LLMError(f"Gemini API error {e.code}: {e}") from e
        raise LLMError(f"Gemini returned unusable output after {self.max_attempts} tries: {last_err}")


class FakeLLM:
    """For tests: you supply a function that returns the object for each call."""

    def __init__(self, responder: Callable[[str, str, type[BaseModel]], BaseModel]):
        self.responder = responder
        self.name = "fake"
        self.calls = 0
        self.prompts: list[str] = []

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        self.calls += 1
        self.prompts.append(prompt)
        out = self.responder(system, prompt, schema)
        return schema.model_validate(out.model_dump() if isinstance(out, BaseModel) else out)


def get_llm(settings: Settings | None = None) -> LLM | None:
    """Returns a Gemini client, or None for offline (rules-only) mode."""
    settings = settings or get_settings()
    if not settings.use_gemini:
        return None
    return GeminiLLM(settings.gemini_api_key, settings.gemini_model, fallbacks=settings.gemini_fallbacks)
