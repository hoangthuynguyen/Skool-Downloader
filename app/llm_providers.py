#!/usr/bin/env python3
"""
Multi-provider LLM catalog + fallback.

Providers (OpenAI-compatible unless noted):
  anthropic  — Claude Messages API
  openai     — OpenAI official
  openrouter — OpenRouter aggregator
  gemini     — Google Gemini (native generateContent)
  glm        — Zhipu GLM (智谱)
  qwen       — Alibaba DashScope Qwen (通义)
  deepseek   — DeepSeek
  kimi       — Moonshot Kimi (月之暗面)  [alias: kiwi]
  siliconflow— SiliconFlow 硅基流动
  doubao     — ByteDance Volcengine Doubao (豆包)
  stepfun    — StepFun 阶跃星辰
  yi         — 01.AI 零一万物
  baichuan   — Baichuan 百川
  minimax    — MiniMax (OpenAI-compat endpoint)
  groq       — Groq
  grok       — xAI Grok (api.x.ai)  [alias: xai]
  custom     — user base_url + key + model

Settings (.settings.json):
  llm_provider: "openrouter"
  llm_fallback: ["openrouter","gemini","grok","qwen","glm","deepseek","kimi","openai","anthropic"]
  llm_providers: {
    "qwen": {"api_key": "...", "model": "qwen-plus", "base_url": "..."},
    "grok": {"api_key": "...", "model": "grok-3-mini"},
    ...
  }
"""
from __future__ import annotations

import json, os, time
from pathlib import Path
from typing import Any

import ai_tools as AI

SETTINGS = AI.SETTINGS_FILE

# Catalog: id -> meta
PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "title": "Claude (Anthropic)",
        "kind": "anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "models": [
            "claude-sonnet-4-6",
            "claude-opus-4-5",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
        "docs": "console.anthropic.com",
    },
    "openai": {
        "title": "OpenAI",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini"],
        "docs": "platform.openai.com",
    },
    "openrouter": {
        "title": "OpenRouter",
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-4o-mini",
        "models": [
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
            "x-ai/grok-3-mini",
            "x-ai/grok-3",
            "deepseek/deepseek-chat",
            "qwen/qwen-2.5-72b-instruct",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        "docs": "openrouter.ai",
        "extra_headers": True,  # HTTP-Referer optional
    },
    "gemini": {
        "title": "Google Gemini",
        "kind": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GEMINI_API_KEY",  # or GOOGLE_API_KEY
        "env_key_alt": "GOOGLE_API_KEY",
        "default_model": "gemini-2.0-flash",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.5-flash-preview-05-20",
        ],
        "docs": "aistudio.google.com",
    },
    "glm": {
        "title": "智谱 GLM (Zhipu)",
        "kind": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "ZHIPU_API_KEY",
        "env_key_alt": "GLM_API_KEY",
        "default_model": "glm-4-flash",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4-long", "glm-z1-air"],
        "docs": "open.bigmodel.cn",
        "region": "cn",
    },
    "qwen": {
        "title": "通义 Qwen (DashScope)",
        "kind": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
        "env_key_alt": "QWEN_API_KEY",
        "default_model": "qwen-plus",
        "models": [
            "qwen-max", "qwen-plus", "qwen-turbo",
            "qwen-long", "qwen2.5-72b-instruct", "qwen2.5-32b-instruct",
        ],
        "docs": "dashscope.console.aliyun.com",
        "region": "cn",
    },
    "deepseek": {
        "title": "DeepSeek",
        "kind": "openai",
        "base_url": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "docs": "platform.deepseek.com",
        "region": "cn",
    },
    "kimi": {
        "title": "Kimi / Moonshot (月之暗面)",
        "kind": "openai",
        "base_url": "https://api.moonshot.cn/v1",
        "env_key": "MOONSHOT_API_KEY",
        "env_key_alt": "KIMI_API_KEY",
        "default_model": "moonshot-v1-128k",
        "models": [
            "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
            "kimi-latest",
        ],
        "docs": "platform.moonshot.cn",
        "region": "cn",
        "aliases": ["kiwi"],  # user typo/common name
    },
    "siliconflow": {
        "title": "SiliconFlow 硅基流动",
        "kind": "openai",
        "base_url": "https://api.siliconflow.cn/v1",
        "env_key": "SILICONFLOW_API_KEY",
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "models": [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "deepseek-ai/DeepSeek-V3",
            "Pro/deepseek-ai/DeepSeek-R1",
            "THUDM/glm-4-9b-chat",
        ],
        "docs": "siliconflow.cn",
        "region": "cn",
    },
    "doubao": {
        "title": "豆包 Doubao (Volcengine)",
        "kind": "openai",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "env_key": "ARK_API_KEY",
        "env_key_alt": "DOUBAO_API_KEY",
        "default_model": "doubao-pro-32k",
        "models": [
            "doubao-pro-32k", "doubao-lite-32k",
            "doubao-1.5-pro-32k", "doubao-1.5-lite-32k",
        ],
        "docs": "console.volcengine.com/ark",
        "region": "cn",
        "note": "Model id may be endpoint id from Volcengine console",
    },
    "stepfun": {
        "title": "阶跃星辰 StepFun",
        "kind": "openai",
        "base_url": "https://api.stepfun.com/v1",
        "env_key": "STEPFUN_API_KEY",
        "default_model": "step-2-16k",
        "models": ["step-2-16k", "step-1-8k", "step-1-32k", "step-1-128k", "step-1-256k"],
        "docs": "platform.stepfun.com",
        "region": "cn",
    },
    "yi": {
        "title": "零一万物 Yi (01.AI)",
        "kind": "openai",
        "base_url": "https://api.lingyiwanwu.com/v1",
        "env_key": "YI_API_KEY",
        "default_model": "yi-lightning",
        "models": ["yi-lightning", "yi-large", "yi-medium", "yi-spark"],
        "docs": "platform.lingyiwanwu.com",
        "region": "cn",
    },
    "baichuan": {
        "title": "百川 Baichuan",
        "kind": "openai",
        "base_url": "https://api.baichuan-ai.com/v1",
        "env_key": "BAICHUAN_API_KEY",
        "default_model": "Baichuan4-Turbo",
        "models": ["Baichuan4-Turbo", "Baichuan4-Air", "Baichuan3-Turbo", "Baichuan3-Turbo-128k"],
        "docs": "platform.baichuan-ai.com",
        "region": "cn",
    },
    "minimax": {
        "title": "MiniMax",
        "kind": "openai",
        "base_url": "https://api.minimax.chat/v1",
        "env_key": "MINIMAX_API_KEY",
        "default_model": "MiniMax-Text-01",
        "models": ["MiniMax-Text-01", "abab6.5s-chat", "abab6.5-chat"],
        "docs": "platform.minimaxi.com",
        "region": "cn",
    },
    "groq": {
        "title": "Groq",
        "kind": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "qwen-qwq-32b",
        ],
        "docs": "console.groq.com",
    },
    "grok": {
        "title": "Grok (xAI)",
        "kind": "openai",
        "base_url": "https://api.x.ai/v1",
        "env_key": "XAI_API_KEY",
        "env_key_alt": "GROK_API_KEY",
        "default_model": "grok-3-mini",
        "models": [
            "grok-3",
            "grok-3-mini",
            "grok-3-fast",
            "grok-3-mini-fast",
            "grok-2-1212",
            "grok-2-vision-1212",
        ],
        "docs": "console.x.ai",
        "note": "OpenAI-compatible Chat Completions at api.x.ai/v1",
    },
    "custom": {
        "title": "Custom OpenAI-compatible",
        "kind": "openai",
        "base_url": "http://127.0.0.1:11434/v1",
        "env_key": "CUSTOM_LLM_API_KEY",
        "default_model": "llama3.2",
        "models": ["llama3.2", "qwen2.5", "deepseek-r1"],
        "docs": "Any OpenAI-compatible endpoint (Ollama, vLLM, …)",
    },
}

# alias map
_ALIASES = {
    "claude": "anthropic",
    "kiwi": "kimi",
    "moonshot": "kimi",
    "zhipu": "glm",
    "dashscope": "qwen",
    "xai": "grok",
    "x-ai": "grok",
}

DEFAULT_FALLBACK = [
    "openrouter", "gemini", "grok", "qwen", "glm", "deepseek", "kimi",
    "siliconflow", "openai", "anthropic", "groq",
]


def normalize_provider(pid: str) -> str:
    p = (pid or "").strip().lower()
    p = _ALIASES.get(p, p)
    return p if p in PROVIDERS else "anthropic"


def list_provider_ids(region: str | None = None) -> list[str]:
    ids = list(PROVIDERS.keys())
    if region == "cn":
        return [i for i in ids if PROVIDERS[i].get("region") == "cn" or i in ("openrouter", "gemini", "openai", "anthropic", "custom")]
    return ids


def provider_meta(pid: str) -> dict:
    pid = normalize_provider(pid)
    return dict(PROVIDERS.get(pid) or PROVIDERS["anthropic"])


def load_settings() -> dict:
    return AI.load_settings()


def save_setting(key, value):
    AI.save_setting(key, value)


def _prov_store() -> dict:
    s = load_settings()
    d = s.get("llm_providers") or {}
    return d if isinstance(d, dict) else {}


def get_provider() -> str:
    s = load_settings()
    return normalize_provider(os.environ.get("LLM_PROVIDER") or s.get("llm_provider") or "anthropic")


def set_provider(pid: str):
    save_setting("llm_provider", normalize_provider(pid))


def get_fallback_chain() -> list[str]:
    s = load_settings()
    raw = s.get("llm_fallback")
    if isinstance(raw, str):
        chain = [normalize_provider(x.strip()) for x in raw.split(",") if x.strip()]
    elif isinstance(raw, list):
        chain = [normalize_provider(str(x)) for x in raw if str(x).strip()]
    else:
        chain = list(DEFAULT_FALLBACK)
    # always include current first if missing
    cur = get_provider()
    if cur not in chain:
        chain = [cur] + chain
    # unique
    seen, out = set(), []
    for p in chain:
        if p not in seen and p in PROVIDERS:
            seen.add(p)
            out.append(p)
    return out or ["anthropic"]


def set_fallback_chain(chain):
    if isinstance(chain, str):
        items = [x.strip() for x in chain.split(",") if x.strip()]
    else:
        items = list(chain or [])
    items = [normalize_provider(x) for x in items]
    save_setting("llm_fallback", items)
    return items


def get_provider_config(pid: str) -> dict:
    """Merge catalog defaults + settings + env."""
    pid = normalize_provider(pid)
    meta = provider_meta(pid)
    store = _prov_store().get(pid) or {}
    s = load_settings()

    # legacy openai_* / anthropic
    api_key = (store.get("api_key") or "").strip()
    if not api_key and pid == "anthropic":
        api_key = AI.get_api_key()
    if not api_key and pid == "openai":
        api_key = (os.environ.get("OPENAI_API_KEY") or s.get("openai_api_key") or "").strip()
    if not api_key:
        env_k = meta.get("env_key")
        env_alt = meta.get("env_key_alt")
        if env_k:
            api_key = (os.environ.get(env_k) or "").strip()
        if not api_key and env_alt:
            api_key = (os.environ.get(env_alt) or "").strip()
        # settings mirror env_key lower
        if not api_key and env_k:
            api_key = (s.get(env_k.lower()) or s.get(f"{pid}_api_key") or "").strip()

    base_url = (store.get("base_url") or meta.get("base_url") or "").rstrip("/")
    if pid == "openai" and s.get("openai_base_url"):
        base_url = str(s.get("openai_base_url")).rstrip("/")
    if pid == "custom" and store.get("base_url"):
        base_url = str(store["base_url"]).rstrip("/")

    model = (store.get("model") or "").strip()
    if not model and pid == "openai" and s.get("openai_model"):
        model = str(s.get("openai_model")).strip()
    if not model and pid == "anthropic":
        model = meta.get("default_model") or AI.DEFAULT_MODEL
    if not model:
        model = meta.get("default_model") or "gpt-4o-mini"

    return {
        "id": pid,
        "title": meta.get("title") or pid,
        "kind": meta.get("kind") or "openai",
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "models": list(meta.get("models") or [model]),
        "docs": meta.get("docs") or "",
        "region": meta.get("region") or "",
        "configured": bool(api_key),
    }


def save_provider_config(pid: str, api_key=None, model=None, base_url=None):
    pid = normalize_provider(pid)
    s = load_settings()
    store = dict(s.get("llm_providers") or {})
    cur = dict(store.get(pid) or {})
    if api_key is not None:
        cur["api_key"] = (api_key or "").strip()
        # keep legacy fields in sync for openai/anthropic
        if pid == "anthropic" and api_key:
            s["anthropic_api_key"] = api_key.strip()
        if pid == "openai" and api_key is not None:
            s["openai_api_key"] = (api_key or "").strip()
    if model is not None:
        cur["model"] = (model or "").strip()
        if pid == "openai":
            s["openai_model"] = cur["model"]
    if base_url is not None:
        cur["base_url"] = (base_url or "").strip().rstrip("/")
        if pid == "openai":
            s["openai_base_url"] = cur["base_url"]
    store[pid] = cur
    s["llm_providers"] = store
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return get_provider_config(pid)


def providers_status() -> dict:
    rows = []
    for pid in PROVIDERS:
        c = get_provider_config(pid)
        rows.append({
            "id": pid,
            "title": c["title"],
            "configured": c["configured"],
            "model": c["model"],
            "kind": c["kind"],
            "region": c.get("region") or "",
        })
    ready = [r for r in rows if r["configured"]]
    return {
        "provider": get_provider(),
        "fallback": get_fallback_chain(),
        "ready_count": len(ready),
        "ready": len(ready) > 0,
        "providers": rows,
    }


# ---------------- API calls ----------------

def _openai_compatible_call(cfg: dict, system: str, user_text: str, max_tokens=8000):
    import requests
    if not cfg.get("api_key"):
        raise RuntimeError(f"Chưa có API key cho {cfg.get('title') or cfg.get('id')}")
    base = (cfg.get("base_url") or "").rstrip("/")
    if not base:
        raise RuntimeError(f"Thiếu base_url cho {cfg.get('id')}")
    url = f"{base}/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_text})
    body = {
        "model": cfg.get("model"),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    # OpenRouter optional headers
    if cfg.get("id") == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/hoangthuynguyen/Skool-Downloader"
        headers["X-Title"] = "Skool Archiver"
    last = ""
    for a in range(3):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=180)
        except Exception as e:
            last = str(e)
            time.sleep(3 * (a + 1))
            continue
        if r.status_code == 200:
            data = r.json()
            # some CN APIs wrap differently
            ch = (data.get("choices") or [{}])[0]
            msg = ch.get("message") or ch.get("delta") or {}
            text = msg.get("content") if isinstance(msg, dict) else None
            if text is None and isinstance(ch.get("text"), str):
                text = ch["text"]
            return (text or "").strip()
        last = f"{r.status_code}: {r.text[:400]}"
        if r.status_code in (429, 500, 502, 503, 529):
            time.sleep(4 * (a + 1))
            continue
        break
    raise RuntimeError(f"{cfg.get('id')} API lỗi → {last}")


def _gemini_call(cfg: dict, system: str, user_text: str, max_tokens=8000):
    import requests
    key = cfg.get("api_key")
    if not key:
        raise RuntimeError("Chưa có Gemini API key (GEMINI_API_KEY / GOOGLE_API_KEY)")
    model = cfg.get("model") or "gemini-2.0-flash"
    base = (cfg.get("base_url") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = f"{base}/models/{model}:generateContent"
    parts = []
    if system:
        # system as first user turn prefix for broad compatibility
        parts.append({"text": f"[System]\n{system}\n\n[User]\n{user_text}"})
    else:
        parts.append({"text": user_text})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.3,
        },
    }
    last = ""
    for a in range(3):
        try:
            r = requests.post(url, params={"key": key}, json=body, timeout=180)
        except Exception as e:
            last = str(e)
            time.sleep(3 * (a + 1))
            continue
        if r.status_code == 200:
            data = r.json()
            cands = data.get("candidates") or []
            if not cands:
                raise RuntimeError(f"Gemini empty response: {str(data)[:200]}")
            content = cands[0].get("content") or {}
            texts = []
            for p in content.get("parts") or []:
                if "text" in p:
                    texts.append(p["text"])
            return "\n".join(texts).strip()
        last = f"{r.status_code}: {r.text[:400]}"
        if r.status_code in (429, 500, 502, 503):
            time.sleep(4 * (a + 1))
            continue
        break
    raise RuntimeError(f"Gemini API lỗi → {last}")


def _anthropic_call(cfg: dict, system: str, user_text: str, max_tokens=8000):
    # reuse ai_tools with optional model override
    key = cfg.get("api_key") or AI.get_api_key()
    if not key:
        raise RuntimeError("Chưa có Claude API key")
    import requests
    body = {
        "model": cfg.get("model") or AI.DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_text}],
    }
    if system:
        body["system"] = system
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    last = ""
    for a in range(3):
        try:
            r = requests.post(AI.API_URL, headers=headers, json=body, timeout=180)
        except Exception as e:
            last = str(e)
            time.sleep(4 * (a + 1))
            continue
        if r.status_code == 200:
            data = r.json()
            return "".join(
                b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
            ).strip()
        last = f"{r.status_code}: {r.text[:300]}"
        if r.status_code in (429, 500, 502, 503, 529):
            time.sleep(5 * (a + 1))
            continue
        break
    raise RuntimeError(f"Claude API lỗi → {last}")


def call_provider(pid: str, system: str, user_text: str, max_tokens=8000, model_override=None):
    cfg = get_provider_config(pid)
    if model_override:
        cfg = dict(cfg)
        cfg["model"] = model_override
    kind = cfg.get("kind") or "openai"
    if kind == "anthropic":
        return _anthropic_call(cfg, system, user_text, max_tokens=max_tokens)
    if kind == "gemini":
        return _gemini_call(cfg, system, user_text, max_tokens=max_tokens)
    return _openai_compatible_call(cfg, system, user_text, max_tokens=max_tokens)


def complete_with_fallback(
    system: str,
    user_text: str,
    provider=None,
    fallback=True,
    max_tokens=8000,
    model=None,
    log=print,
):
    """
    Try primary provider then fallback chain of configured providers.
    Returns (text, used_provider).
    """
    primary = normalize_provider(provider or get_provider())
    if fallback:
        chain = get_fallback_chain()
        if primary in chain:
            chain = [primary] + [p for p in chain if p != primary]
        else:
            chain = [primary] + chain
    else:
        chain = [primary]

    # only try configured (except force primary once)
    errors = []
    for i, pid in enumerate(chain):
        cfg = get_provider_config(pid)
        if not cfg.get("configured") and not (i == 0 and pid == primary):
            continue
        if not cfg.get("configured"):
            errors.append(f"{pid}: no key")
            continue
        try:
            log(f"   LLM try [{pid}] model={model or cfg.get('model')}…")
            text = call_provider(pid, system, user_text, max_tokens=max_tokens, model_override=model)
            if text:
                if pid != primary:
                    log(f"   ✓ fallback OK via {pid}")
                return text, pid
            errors.append(f"{pid}: empty")
        except Exception as e:
            errors.append(f"{pid}: {e}")
            log(f"   ✗ {pid}: {e}")
            continue
    raise RuntimeError("Tất cả LLM provider thất bại:\n- " + "\n- ".join(errors[:12]))
