"""LLM client (spec §11.1): one function, ``complete(system, user) -> str``.

* Every request/response pair is cached by a SHA-256 hash of (model, system, user, max_tokens) in
  ``cache/llm/``. A cache hit never touches the network, so cached demo answers work offline (§0.8).
* If there is no cached answer and the call cannot be made (SDK not installed, no credentials,
  network down, refusal, ``EMBER_LLM_OFFLINE=1``), ``LLMUnavailable`` is raised. Callers then use
  their deterministic fallback (template narration, rule-based parser). Nothing is invented here.
* Provider: Anthropic Messages API through the official ``anthropic`` SDK (optional extra
  ``uv sync --extra llm``). Model via ``EMBER_LLM_MODEL`` (default ``claude-opus-5-5``).
* Temperature: the spec asks for 0, but current Claude models reject sampling parameters, so none
  are sent. Reproducibility comes from the cache: the same prompt always replays the same answer.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from ember.paths import CACHE_DIR

DEFAULT_MODEL = "claude-opus-5-5"
LLM_CACHE_DIR = CACHE_DIR / "llm"
# Models that accept the server-side refusal fallback ("default" routing by refusal category).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    """No cached answer and no way to get a live one. Callers fall back to deterministic code."""


def model_name() -> str:
    return os.environ.get("EMBER_LLM_MODEL", DEFAULT_MODEL)


def offline() -> bool:
    return os.environ.get("EMBER_LLM_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def cache_key(model: str, system: str, user: str, max_tokens: int) -> str:
    blob = json.dumps(
        {"model": model, "system": system, "user": user, "max_tokens": max_tokens},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cached(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    cache_dir: Path | None = None,
) -> str | None:
    """The cached response for this exact request, or None."""
    m = model or model_name()
    path = (cache_dir or LLM_CACHE_DIR) / f"{cache_key(m, system, user, max_tokens)}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    return None


def _call_anthropic(model: str, system: str, user: str, max_tokens: int) -> tuple[str, str | None]:
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailable("anthropic SDK not installed (uv sync --extra llm)") from exc
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise LLMUnavailable("no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN set")
    client = anthropic.Anthropic(timeout=60.0, max_retries=1)
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if model in FALLBACK_MODELS:
        kwargs["betas"] = [FALLBACK_BETA]
        kwargs["fallbacks"] = "default"
    try:
        resp = client.beta.messages.create(**kwargs)
    except anthropic.APIConnectionError as exc:
        raise LLMUnavailable(f"network error: {exc}") from exc
    except anthropic.RateLimitError as exc:
        raise LLMUnavailable("rate limited") from exc
    except anthropic.APIStatusError as exc:
        raise LLMUnavailable(f"API error {exc.status_code}: {exc.message}") from exc
    if resp.stop_reason == "refusal":
        raise LLMUnavailable("model declined the request")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise LLMUnavailable(f"empty response (stop_reason={resp.stop_reason})")
    return text, getattr(resp, "_request_id", None)


def complete(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    cache_dir: Path | None = None,
) -> str:
    """Cached completion. Raises ``LLMUnavailable`` when there is no cached or live answer."""
    m = model or model_name()
    d = cache_dir or LLM_CACHE_DIR
    hit = cached(system, user, model=m, max_tokens=max_tokens, cache_dir=d)
    if hit is not None:
        return hit
    if offline():
        raise LLMUnavailable("offline mode (EMBER_LLM_OFFLINE=1) and no cached answer")
    text, request_id = _call_anthropic(m, system, user, max_tokens)
    d.mkdir(parents=True, exist_ok=True)
    record = {
        "model": m,
        "max_tokens": max_tokens,
        "system": system,
        "user": user,
        "response": text,
        "request_id": request_id,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (d / f"{cache_key(m, system, user, max_tokens)}.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return text
