"""LLM access. Stays free: Gemini Flash/Flash-Lite by default; OpenRouter DeepSeek
(also free tier) used for the heavier rewrite if OPENROUTER_API_KEY is set.

Everything returns parsed JSON via a tolerant extractor so a stray ``` fence or
prose preamble never crashes the pipeline."""
from __future__ import annotations
import os
import re
import json
from typing import Optional

GEMINI_KEY = lambda: os.getenv("GEMINI_API_KEY", "").strip()
OPENROUTER_KEY = lambda: os.getenv("OPENROUTER_API_KEY", "").strip()

GEMINI_FAST = "gemini-2.5-flash-lite"     # extraction (cheap, ~1000/day free)
GEMINI_SMART = "gemini-2.5-flash"          # critique / fallback rewrite (~250/day free)
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def strip_to_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1 and e > s:
        t = t[s:e + 1]
    return t


def _gemini(model: str, system: str, prompt: str, temperature: float) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_KEY())
    cfg = types.GenerateContentConfig(
        system_instruction=system, response_mime_type="application/json", temperature=temperature)
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    return resp.text


def _openrouter(system: str, prompt: str, temperature: float) -> str:
    from openai import OpenAI
    oc = OpenAI(base_url=OPENROUTER_BASE, api_key=OPENROUTER_KEY())
    resp = oc.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=temperature, response_format={"type": "json_object"},
        extra_headers={"HTTP-Referer": "http://localhost", "X-Title": "ResumeTailorPro"})
    return resp.choices[0].message.content


_TRANSIENT = ("503", "unavailable", "429", "resource_exhausted", "overloaded",
              "high demand", "rate limit", "timeout", "timed out", "temporarily", "500", "502", "504")


def _run_engine(engine: str, system: str, prompt: str, temperature: float) -> str:
    if engine == "openrouter":
        return _openrouter(system, prompt, temperature)
    if engine == "gemini_fast":
        return _gemini(GEMINI_FAST, system, prompt, temperature)
    return _gemini(GEMINI_SMART, system, prompt, temperature)


def call_json(system: str, prompt: str, *, heavy: bool = False, temperature: float = 0.1,
              retries: int = 3) -> dict:
    """Return parsed JSON. heavy=True prefers DeepSeek (rewrite); else Gemini Flash.
    Each engine is retried with backoff on TRANSIENT errors (503/429/overload) before
    falling through to the next, so a momentary spike never silently drops the rewrite."""
    import time
    # build engine order, then dedupe preserving order
    order = (["openrouter"] if (heavy and OPENROUTER_KEY()) else [])
    order += (["gemini_smart", "gemini_fast"] if heavy else ["gemini_fast", "gemini_smart"])
    seen = set()
    order = [e for e in order if not (e in seen or seen.add(e))]

    last_err = None
    for engine in order:
        for attempt in range(retries):
            try:
                raw = _run_engine(engine, system, prompt, temperature)
                return json.loads(strip_to_json(raw))
            except Exception as e:      # noqa: BLE001
                last_err = e
                msg = str(e).lower()
                transient = any(t in msg for t in _TRANSIENT)
                if transient and attempt < retries - 1:
                    time.sleep(1.5 * (attempt + 1) + 0.5)   # 2s, 3.5s, 5s backoff
                    continue
                break    # non-transient, or retries exhausted -> next engine
    raise RuntimeError(f"All LLM engines failed. Last error: {last_err}")


def have_any_key() -> bool:
    return bool(GEMINI_KEY() or OPENROUTER_KEY())
