"""Narrators: the injected prose layer (§0 rule 3 — narrates, never calculates).

- ClaudeNarrator: the Claude API at temperature 0 (server-side key only, §15).
- TemplateNarrator: deterministic, offline — used by tests and as the honest
  fallback when no API key exists (its output is clearly labelled machine
  templating, not analysis).
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


def default_narrator():
    """Claude when a key exists, labelled template otherwise."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeNarrator()
    return TemplateNarrator()
