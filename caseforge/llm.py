"""The only file that talks to an LLM. Swap providers here without touching the pipeline."""

from __future__ import annotations

import json
import time
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    name: str
    calls: int

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T: ...


class GeminiLLM:
    """Google Gemini via the official `google-genai` SDK, with JSON-schema output."""

    def __init__(self, api_key: str, model: str, max_attempts: int = 4):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set. Put it in your .env file.")
        from google import genai  # imported lazily so offline mode needs no SDK

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.name = f"gemini:{model}"
        self.max_attempts = max_attempts
        self.calls = 0

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        from google.genai import errors, types

        last_err: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self.calls += 1
                resp = self._client.models.generate_content(
                    model=self.model,
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
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                # Badly shaped output: ask again. "Correct shape every time" is enforced here.
                last_err = e
            except errors.APIError as e:
                last_err = e
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_attempts:
                    time.sleep(min(60, 5 * 2 ** (attempt - 1)))  # free-tier rate limits
                    continue
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
    return GeminiLLM(settings.gemini_api_key, settings.gemini_model)
