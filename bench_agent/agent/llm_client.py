import os
import time
import hashlib
import json
from pathlib import Path
from openai import OpenAI
from typing import Optional

# Cache directory for LLM responses (deterministic mode)
CACHE_DIR = Path(".llm_cache")
CACHE_DIR.mkdir(exist_ok=True)


def make_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def _compute_cache_key(model: str, messages: list[dict], temperature: float) -> str:
    """Compute cache key for deterministic LLM calls."""
    cache_input = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    content = json.dumps(cache_input, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def _get_cached_response(cache_key: str) -> Optional[str]:
    """Get cached LLM response if available."""
    cache_file = CACHE_DIR / f"{cache_key}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding='utf-8')
    return None


def _save_cached_response(cache_key: str, response: str) -> None:
    """Save LLM response to cache."""
    cache_file = CACHE_DIR / f"{cache_key}.txt"
    cache_file.write_text(response, encoding='utf-8')


def chat(
    client: OpenAI,
    model: str,
    messages: list[dict],
    temperature: float = 0.0,  # P0-2: Default to 0 for deterministic outputs
    max_retries: int = 3,
    use_cache: bool = True
) -> str:
    """
    Chat with LLM with retry logic and caching.

    P0-2 Enhancement:
    - temperature=0 for deterministic outputs (BRS stability)
    - Exponential backoff retry for robustness
    - Response caching to reduce API calls

    Args:
        client: OpenAI client
        model: Model name (e.g., "gpt-4o-mini")
        messages: List of message dicts
        temperature: Sampling temperature (0.0 = deterministic)
        max_retries: Maximum number of retry attempts
        use_cache: Enable response caching

    Returns:
        LLM response text
    """
    # Check cache first (only for temperature=0 deterministic calls)
    if use_cache and temperature == 0.0:
        cache_key = _compute_cache_key(model, messages, temperature)
        cached = _get_cached_response(cache_key)
        if cached is not None:
            return cached

    # Retry loop with exponential backoff
    last_exception = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            response_text = resp.choices[0].message.content or ""

            # Save to cache if deterministic
            if use_cache and temperature == 0.0:
                cache_key = _compute_cache_key(model, messages, temperature)
                _save_cached_response(cache_key, response_text)

            return response_text

        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt seconds
                wait_time = 2 ** attempt
                print(f"[llm_client] API call failed (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s: {e}", flush=True)
                time.sleep(wait_time)
            else:
                # Final attempt failed
                print(f"[llm_client] API call failed after {max_retries} attempts: {e}", flush=True)

    # All retries exhausted
    raise RuntimeError(f"LLM API call failed after {max_retries} attempts") from last_exception
