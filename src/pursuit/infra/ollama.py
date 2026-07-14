"""OllamaClient — the $0 local-LLM transport for banter (D8 LLM mode).

A thin httpx wrapper over the Ollama REST API with a hard per-call deadline.
Every network/parse failure is funnelled into :class:`OllamaError` so the talk
layer (:class:`~pursuit.strategy.ollama_talk.OllamaTalk`) can catch a single type
and fall back to zero-token templates. No game parameters live here — temperatures
and token budgets are passed by the caller or defaulted per Ollama's own API.
"""

from __future__ import annotations

from typing import Any

import httpx

#: Near-deterministic sampling for the interpreter helper (STRATEGY §8 classify path).
_CLASSIFY_TEMPERATURE = 0.1


class OllamaError(RuntimeError):
    """Any Ollama call that timed out, errored, or returned an unusable body."""


class OllamaClient:
    """POST /api/generate wrapper with an is_up() ping; never raises past OllamaError."""

    def __init__(self, base_url: str, model: str, timeout_s: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = float(timeout_s)

    def is_up(self, ping_timeout_s: float = 1.0) -> bool:
        """GET /api/tags with a short timeout so callers can detect Ollama absence."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=ping_timeout_s)
        except httpx.HTTPError:
            return False
        return resp.status_code == 200

    def generate(self, prompt: str, system: str | None = None,
                 options: dict[str, Any] | None = None,
                 timeout: float | None = None) -> str:
        """Blocking single-shot completion; returns the model's ``response`` text."""
        body: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
        if system is not None:
            body["system"] = system
        if options:
            body["options"] = dict(options)
        return self._post(body, timeout)

    def classify(self, prompt: str, system: str | None = None,
                 options: dict[str, Any] | None = None,
                 timeout: float | None = None) -> str:
        """Interpreter helper — pins temperature 0.1 unless the caller overrides it."""
        merged: dict[str, Any] = {"temperature": _CLASSIFY_TEMPERATURE}
        if options:
            merged.update(options)
        return self.generate(prompt, system=system, options=merged, timeout=timeout)

    def _post(self, body: dict[str, Any], timeout: float | None) -> str:
        """Single hard-deadline POST; the ONLY place httpx exceptions cross into ours."""
        deadline = self.timeout_s if timeout is None else float(timeout)
        try:
            resp = httpx.post(f"{self.base_url}/api/generate", json=body, timeout=deadline)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:  # ValueError covers JSONDecodeError
            raise OllamaError(f"ollama generate failed: {exc}") from exc
        response = data.get("response") if isinstance(data, dict) else None
        if not isinstance(response, str):
            raise OllamaError(f"ollama returned no 'response' string: {data!r}")
        return response
