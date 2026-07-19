"""Narrators: the injected prose layer (§0 rule 3 — narrates, never calculates).

- ClaudeNarrator: the Claude API at temperature 0 (server-side key only, §15).
- GroqNarrator: DOCUMENTED STACK DEVIATION (owner-authorized 2026-07-19) — the
  spec stack names the Claude API; the project owner supplied a Groq key
  instead. OpenAI-compatible endpoint, temperature 0. Memo records carry the
  narrator class name, so which backend narrated is always auditable.
- TemplateNarrator: deterministic, offline — used by tests and as the honest
  fallback when no API key exists (its output is clearly labelled machine
  templating, not analysis).

Narration can never change a number: the §11.3 quant hash excludes prose.
"""

from __future__ import annotations

import os


class TemplateNarrator:
    """Deterministic stand-in. Output is labelled so a template memo can never
    pass as an analyst's narrative."""

    def __call__(self, system: str, user: str) -> str:
        head = system.split(".")[0].strip()
        return (
            f"[template narration — no LLM key configured] {head}. "
            f"Facts as provided by tools: {user[:400]}"
        )


class ClaudeNarrator:
    MODEL = "claude-sonnet-5"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — narration unavailable")
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model or self.MODEL

    def __call__(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=700,
            temperature=0.0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()


class GroqNarrator:
    """Owner-authorized deviation from the Claude-API stack (see module doc).
    Model verified against /models on 2026-07-19; llama-3.3-70b-versatile is
    the default, overridable via GROQ_MODEL."""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set — narration unavailable")
        self._key = key
        self._model = model or os.environ.get("GROQ_MODEL", self.DEFAULT_MODEL)

    def __call__(self, system: str, user: str) -> str:
        import time

        import httpx

        last_detail = ""
        for attempt in range(6):
            resp = httpx.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "temperature": 0.0,
                    "max_tokens": 700,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=60.0,
            )
            if resp.status_code == 429:  # free-tier rate limit — honor Retry-After
                retry_after = resp.headers.get("retry-after")
                last_detail = f"retry-after={retry_after} body={resp.text[:300]}"
                wait = float(retry_after or 2 ** (attempt + 1))
                if wait > 300.0:
                    # daily-quota-style limit: waiting inside this call is
                    # pointless — surface it so the caller can fall back honestly
                    break
                time.sleep(min(wait + 0.5, 60.0))
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        raise RuntimeError(f"Groq rate limit persisted through backoff ({last_detail})")


def default_narrator():
    """Claude if configured; else the owner-authorized Groq backend; else the
    labelled template."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeNarrator()
    if os.environ.get("GROQ_API_KEY"):
        return GroqNarrator()
    return TemplateNarrator()
