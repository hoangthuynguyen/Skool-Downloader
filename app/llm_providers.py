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
        # Defaults: DeepSeek V4 Flash → MiMo-V2.5 (OpenRouter rankings)
        "default_model": "deepseek/deepseek-v4-flash",
        "models": [
            "deepseek/deepseek-v4-flash",
            "xiaomi/mimo-v2.5",
            "tencent/hy3:free",
            "minimax/minimax-m3",
            "z-ai/glm-5.2",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "deepseek/deepseek-v4-pro",
            "anthropic/claude-opus-4.8",
            "anthropic/claude-opus-4.7",
            "stepfun/step-3.7-flash",
            "anthropic/claude-sonnet-4.6",
            "anthropic/claude-sonnet-5",
            "google/gemini-3-flash-preview",
            "openai/gpt-5.5",
            "xiaomi/mimo-v2.5-pro",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-flash-lite",
            "poolside/laguna-m.1:free",
            "google/gemini-3.1-flash-lite",
            "openai/gpt-oss-120b",
            "openai/gpt-4o-mini",
            "google/gemini-2.0-flash-001",
        ],
        "docs": "openrouter.ai/rankings",
        "extra_headers": True,  # HTTP-Referer optional
        "note": "Primary hub — paste OPENROUTER_API_KEY; pick models per task below",
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
            "gemini-2.5-flash",
            "gemini-2.5-flash-preview-05-20",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "docs": "aistudio.google.com",
        "note": "Mặc định fallback Lesson Summary (Flash)",
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
        # deepseek-chat = model chat mới (V3/V3.2 family trên platform)
        "default_model": "deepseek-chat",
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
            "deepseek-chat-v3",  # alias/gợi ý nếu provider hỗ trợ
        ],
        "docs": "platform.deepseek.com",
        "region": "cn",
        "note": "Mặc định primary cho Lesson Summary (VI)",
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

# Mac dinh: DeepSeek chinh, Gemini Flash phu (co the doi trong GUI / settings)
DEFAULT_FALLBACK = [
    "deepseek", "gemini", "openrouter", "grok", "qwen", "glm", "kimi",
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
    # Mac dinh openrouter (DeepSeek V4 Flash + MiMo fallback per task)
    return normalize_provider(
        os.environ.get("LLM_PROVIDER") or s.get("llm_provider") or "openrouter"
    )


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


# ---- OpenRouter ranked catalog (curated from openrouter.ai/rankings) ----
# pricing_prompt / pricing_completion = USD per token (OpenRouter API style)
OPENROUTER_RANKED: list[dict[str, Any]] = [
    {"id": "tencent/hy3:free", "title": "Hy3 (free)", "vendor": "tencent", "in": 0.0, "out": 0.0},
    {"id": "xiaomi/mimo-v2.5", "title": "MiMo-V2.5", "vendor": "xiaomi", "in": 0.14e-6, "out": 0.28e-6},
    {"id": "deepseek/deepseek-v4-flash", "title": "DeepSeek V4 Flash", "vendor": "deepseek", "in": 0.098e-6, "out": 0.196e-6},
    {"id": "minimax/minimax-m3", "title": "MiniMax M3", "vendor": "minimax", "in": 0.3e-6, "out": 1.2e-6},
    {"id": "z-ai/glm-5.2", "title": "GLM 5.2", "vendor": "z-ai", "in": 0.875e-6, "out": 2.75e-6},
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "title": "Nemotron 3 Ultra (free)", "vendor": "nvidia", "in": 0.0, "out": 0.0},
    {"id": "deepseek/deepseek-v4-pro", "title": "DeepSeek V4 Pro", "vendor": "deepseek", "in": 0.14e-6, "out": 0.28e-6},
    {"id": "anthropic/claude-opus-4.8", "title": "Claude Opus 4.8", "vendor": "anthropic", "in": 5e-6, "out": 25e-6},
    {"id": "anthropic/claude-opus-4.7", "title": "Claude Opus 4.7", "vendor": "anthropic", "in": 5e-6, "out": 25e-6},
    {"id": "stepfun/step-3.7-flash", "title": "Step 3.7 Flash", "vendor": "stepfun", "in": 0.2e-6, "out": 1.15e-6},
    {"id": "anthropic/claude-sonnet-4.6", "title": "Claude Sonnet 4.6", "vendor": "anthropic", "in": 3e-6, "out": 15e-6},
    {"id": "anthropic/claude-sonnet-5", "title": "Claude Sonnet 5", "vendor": "anthropic", "in": 2e-6, "out": 10e-6},
    {"id": "google/gemini-3-flash-preview", "title": "Gemini 3 Flash Preview", "vendor": "google", "in": 0.5e-6, "out": 3e-6},
    {"id": "openai/gpt-5.5", "title": "GPT-5.5", "vendor": "openai", "in": 5e-6, "out": 30e-6},
    {"id": "xiaomi/mimo-v2.5-pro", "title": "MiMo-V2.5-Pro", "vendor": "xiaomi", "in": 0.435e-6, "out": 0.87e-6},
    {"id": "google/gemini-2.5-flash", "title": "Gemini 2.5 Flash", "vendor": "google", "in": 0.3e-6, "out": 2.5e-6},
    {"id": "google/gemini-2.5-flash-lite", "title": "Gemini 2.5 Flash Lite", "vendor": "google", "in": 0.1e-6, "out": 0.4e-6},
    {"id": "poolside/laguna-m.1:free", "title": "Laguna M.1 (free)", "vendor": "poolside", "in": 0.0, "out": 0.0},
    {"id": "google/gemini-3.1-flash-lite", "title": "Gemini 3.1 Flash Lite", "vendor": "google", "in": 0.25e-6, "out": 1.5e-6},
    {"id": "openai/gpt-oss-120b", "title": "gpt-oss-120b", "vendor": "openai", "in": 0.037e-6, "out": 0.17e-6},
]

# Default primary / fallback model ids (OpenRouter)
DEFAULT_PRIMARY_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_FALLBACK_MODEL = "xiaomi/mimo-v2.5"

# ---- Per-task LLM routing (Dashboard) ----
# Defaults: OpenRouter primary DeepSeek V4 Flash → fallback MiMo-V2.5
_OR = "openrouter"
_DM = DEFAULT_PRIMARY_MODEL
_FM = DEFAULT_FALLBACK_MODEL

LLM_TASKS: dict[str, dict[str, Any]] = {
    "research": {
        "title": "Market research",
        "desc": "Nghiên cứu thị trường / report DOCX",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 0,  # course-level
        "est_out_per_lesson": 0,
        "est_in_course": 25000,
        "est_out_course": 10000,
    },
    "structure": {
        "title": "Cấu trúc khóa mới",
        "desc": "Outline chương/bài từ report",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_course": 20000, "est_out_course": 8000,
        "est_in_per_lesson": 0, "est_out_per_lesson": 0,
    },
    "summary": {
        "title": "Summary từng bài",
        "desc": "summary.vi.md — Purpose / takeaways / todo",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 4000, "est_out_per_lesson": 1500,
        "est_in_course": 0, "est_out_course": 0,
    },
    "assets": {
        "title": "Asset pack (script/workshop)",
        "desc": "lesson · talking_script · workshop · quiz",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 6000, "est_out_per_lesson": 4000,
        "est_in_course": 0, "est_out_course": 0,
    },
    "localize": {
        "title": "Dịch / địa phương hóa",
        "desc": "Localize hub — nhiều ngôn ngữ",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 5000, "est_out_per_lesson": 5000,
        "est_in_course": 0, "est_out_course": 0,
        "locale_multiplier": 10,  # ~10 locales T1
    },
    "translate": {
        "title": "Dịch nhanh (export)",
        "desc": "Dịch file tổng hợp / prompt dịch",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_course": 15000, "est_out_course": 15000,
        "est_in_per_lesson": 0, "est_out_per_lesson": 0,
    },
    "image_gen": {
        "title": "Image generation (prompt)",
        "desc": "Prompt ảnh / thumbnail copy (text LLM)",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 800, "est_out_per_lesson": 600,
        "est_in_course": 0, "est_out_course": 0,
    },
    "video_gen": {
        "title": "Video generation (script)",
        "desc": "Talking script / b-roll cues cho AI video",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 3000, "est_out_per_lesson": 2500,
        "est_in_course": 0, "est_out_course": 0,
    },
    "qa": {
        "title": "QA / fact-check",
        "desc": "Loc QA · fact-check LLM sample",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_per_lesson": 3500, "est_out_per_lesson": 800,
        "est_in_course": 0, "est_out_course": 0,
    },
    "prompt": {
        "title": "LLM Prompt / rewrite",
        "desc": "Prompt tùy chỉnh Xuất & Báo cáo",
        "provider": _OR, "model": _DM, "fallback": _OR, "fallback_model": _FM,
        "est_in_course": 8000, "est_out_course": 4000,
        "est_in_per_lesson": 0, "est_out_per_lesson": 0,
    },
}


def list_llm_tasks() -> list[str]:
    return list(LLM_TASKS.keys())


def get_task_llm(task: str) -> dict[str, Any]:
    """Lấy provider/model/fallback cho 1 tác vụ (settings > defaults)."""
    task = (task or "prompt").strip().lower()
    base = dict(LLM_TASKS.get(task) or LLM_TASKS["prompt"])
    s = load_settings()
    store = s.get("llm_tasks") or {}
    if not isinstance(store, dict):
        store = {}
    cur = store.get(task) or {}
    # legacy: summary uses lesson_summary_* keys (then migrate below)
    if task == "summary" and not cur:
        try:
            import config as Cfg
            leg = Cfg.get_lesson_summary_llm() or {}
            if leg:
                cur = {
                    "provider": leg.get("provider"),
                    "model": leg.get("model"),
                    "fallback": (
                        (leg.get("fallback") or [None])[0]
                        if isinstance(leg.get("fallback"), list)
                        else leg.get("fallback")
                    ),
                    "fallback_model": leg.get("fallback_model"),
                }
        except Exception:
            pass
    provider = normalize_provider(cur.get("provider") or base["provider"])
    model = (cur.get("model") or base["model"] or "").strip()
    fb = normalize_provider(cur.get("fallback") or base["fallback"])
    fb_model = (cur.get("fallback_model") or base["fallback_model"] or "").strip()
    # migrate legacy short names → OpenRouter ranking defaults
    legacy = {"deepseek-chat", "deepseek-reasoner", "deepseek-chat-v3", "gemini-2.0-flash", "gpt-4o-mini"}
    if model in legacy or (model and "/" not in model and provider in ("deepseek", "gemini")):
        provider = "openrouter"
        model = DEFAULT_PRIMARY_MODEL
    if fb_model in legacy or (fb_model and "/" not in fb_model and fb in ("deepseek", "gemini")):
        fb = "openrouter"
        fb_model = DEFAULT_FALLBACK_MODEL
    # if model empty, use provider default
    if not model:
        model = get_provider_config(provider).get("model") or base["model"]
    if not fb_model:
        fb_model = get_provider_config(fb).get("model") or base["fallback_model"]
    return {
        "task": task,
        "title": base.get("title") or task,
        "desc": base.get("desc") or "",
        "provider": provider,
        "model": model,
        "fallback": fb,
        "fallback_model": fb_model,
    }


def set_task_llm(
    task: str,
    provider=None,
    model=None,
    fallback=None,
    fallback_model=None,
) -> dict:
    task = (task or "").strip().lower()
    if task not in LLM_TASKS:
        task = "prompt"
    s = load_settings()
    store = dict(s.get("llm_tasks") or {})
    cur = dict(store.get(task) or {})
    if provider is not None:
        cur["provider"] = normalize_provider(provider)
    if model is not None:
        cur["model"] = str(model).strip()
    if fallback is not None:
        cur["fallback"] = normalize_provider(fallback)
    if fallback_model is not None:
        cur["fallback_model"] = str(fallback_model).strip()
    store[task] = cur
    s["llm_tasks"] = store
    # keep legacy summary keys in sync
    if task == "summary":
        if "provider" in cur:
            s["lesson_summary_provider"] = cur["provider"]
        if "model" in cur:
            s["lesson_summary_model"] = cur["model"]
        if "fallback" in cur:
            s["lesson_summary_fallback"] = [cur["fallback"]]
        if "fallback_model" in cur:
            s["lesson_summary_fallback_model"] = cur["fallback_model"]
    try:
        SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        save_setting("llm_tasks", store)
    return get_task_llm(task)


def complete_for_task(
    task: str,
    system: str,
    user_text: str,
    max_tokens: int = 8000,
    log=print,
):
    """
    Gọi LLM theo cấu hình tác vụ (primary model → fallback model).
    Hỗ trợ cùng provider (OpenRouter) với 2 model khác nhau.
    Returns (text, used_label).
    """
    cfg = get_task_llm(task)
    primary = cfg["provider"]
    model = cfg["model"]
    fb = cfg["fallback"]
    fb_model = cfg["fallback_model"]

    # attempts: (provider, model_override, label)
    attempts: list[tuple[str, str | None, str]] = [
        (primary, model, f"{primary}/{model}"),
    ]
    if fb_model and (fb != primary or fb_model != model):
        attempts.append((fb, fb_model, f"{fb}/{fb_model}"))
    for p in get_fallback_chain():
        if all(p != a[0] or (a[1] or "") == "" for a in attempts):
            attempts.append((p, None, p))

    errors = []
    for pid, m_override, label in attempts:
        pcfg = get_provider_config(pid)
        if not pcfg.get("configured"):
            errors.append(f"{label}: no key")
            continue
        try:
            log(f"   LLM[{task}] try [{label}]…")
            text = call_provider(
                pid, system, user_text, max_tokens=max_tokens, model_override=m_override
            )
            if text:
                if label != attempts[0][2]:
                    log(f"   ✓ [{task}] fallback OK via {label}")
                return text, label
            errors.append(f"{label}: empty")
        except Exception as e:
            errors.append(f"{label}: {e}")
            log(f"   ✗ [{task}] {label}: {e}")
            continue
    raise RuntimeError(
        f"LLM task «{task}» thất bại:\n- " + "\n- ".join(errors[:12])
    )


def openrouter_model_choices() -> list[str]:
    """Danh sách model id cho dropdown (ranked + provider catalog)."""
    ids = [m["id"] for m in OPENROUTER_RANKED]
    # merge cache from last refresh
    s = load_settings()
    cached = s.get("openrouter_models_cache") or {}
    for mid in cached.get("ids") or []:
        if mid not in ids:
            ids.append(mid)
    for mid in PROVIDERS.get("openrouter", {}).get("models") or []:
        if mid not in ids:
            ids.append(mid)
    return ids


def openrouter_model_labels() -> list[str]:
    """Nhãn hiển thị: Title (vendor) · id"""
    labels = []
    seen = set()
    for m in OPENROUTER_RANKED:
        lab = f"{m['title']} · {m['id']}"
        labels.append(lab)
        seen.add(m["id"])
    for mid in openrouter_model_choices():
        if mid not in seen:
            labels.append(mid)
            seen.add(mid)
    return labels


def model_id_from_label(label: str) -> str:
    lab = (label or "").strip()
    if " · " in lab:
        return lab.split(" · ")[-1].strip()
    return lab


def label_for_model(model_id: str) -> str:
    mid = (model_id or "").strip()
    for m in OPENROUTER_RANKED:
        if m["id"] == mid:
            return f"{m['title']} · {m['id']}"
    return mid


def pricing_for_model(model_id: str) -> tuple[float, float]:
    """USD per token (prompt, completion)."""
    mid = (model_id or "").strip()
    for m in OPENROUTER_RANKED:
        if m["id"] == mid:
            return float(m.get("in") or 0), float(m.get("out") or 0)
    # cache
    s = load_settings()
    prices = (s.get("openrouter_models_cache") or {}).get("pricing") or {}
    if mid in prices:
        p = prices[mid]
        return float(p.get("in") or 0), float(p.get("out") or 0)
    # cheap default guess
    if ":free" in mid or mid.endswith("/free"):
        return 0.0, 0.0
    return 0.5e-6, 1.5e-6


def refresh_openrouter_models(log=print) -> dict:
    """
    Làm mới danh sách/pricing từ OpenRouter API
    (https://openrouter.ai/api/v1/models — rankings: openrouter.ai/rankings).
    """
    import urllib.request

    url = "https://openrouter.ai/api/v1/models"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SkoolDownloader/3.3",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    models = data.get("data") or []
    ids = []
    pricing = {}
    # prioritize curated ranked ids first
    ranked_ids = {m["id"] for m in OPENROUTER_RANKED}
    for m in models:
        mid = m.get("id") or ""
        if not mid:
            continue
        p = m.get("pricing") or {}
        try:
            pin = float(p.get("prompt") or 0)
            pout = float(p.get("completion") or 0)
        except Exception:
            pin = pout = 0.0
        pricing[mid] = {"in": pin, "out": pout, "name": m.get("name") or mid}
        if mid in ranked_ids or any(
            k in mid
            for k in (
                "deepseek-v4",
                "mimo-v2.5",
                "minimax-m3",
                "glm-5",
                "nemotron-3-ultra",
                "claude-opus-4",
                "claude-sonnet-4",
                "claude-sonnet-5",
                "gemini-3",
                "gemini-2.5-flash",
                "gpt-5.5",
                "gpt-oss-120b",
                "hy3",
                "step-3.7",
                "laguna-m.1",
            )
        ):
            ids.append(mid)
    # update OPENROUTER provider models list in settings cache
    # keep ranked order first
    ordered = [m["id"] for m in OPENROUTER_RANKED]
    for mid in ids:
        if mid not in ordered:
            ordered.append(mid)
    cache = {
        "at": time.strftime("%Y-%m-%d %H:%M"),
        "source": "https://openrouter.ai/api/v1/models",
        "rankings_url": "https://openrouter.ai/rankings#leaderboard-table",
        "ids": ordered[:80],
        "pricing": pricing,
        "total_api_models": len(models),
    }
    s = load_settings()
    s["openrouter_models_cache"] = cache
    # also bump openrouter models list in catalog via settings store default model list
    store = dict(s.get("llm_providers") or {})
    or_cfg = dict(store.get("openrouter") or {})
    if not or_cfg.get("model"):
        or_cfg["model"] = DEFAULT_PRIMARY_MODEL
    store["openrouter"] = or_cfg
    s["llm_providers"] = store
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    # live-update PROVIDERS models for this process
    PROVIDERS["openrouter"]["models"] = ordered[:40]
    log(f">> OpenRouter models refreshed: {len(ordered)} curated · API total {len(models)}")
    return cache


def estimate_course_llm_cost(
    root=None,
    lessons: int | None = None,
    locales: int | None = None,
    tasks: list[str] | None = None,
) -> dict:
    """
    Ước lượng USD nếu chạy các task LLM với model đang chọn.
    Dựa trên token estimate / bài (LLM_TASKS) × số bài × pricing OpenRouter.
    """
    from pathlib import Path

    n_lessons = lessons
    n_locales = locales
    course_name = ""
    if root is not None:
        root = Path(root)
        course_name = root.name
        if n_lessons is None:
            # inventory or upgrade structure
            inv = root / "_upgrade_inventory.json"
            st = root / "_upgrade_new_structure.json"
            if inv.exists():
                try:
                    n_lessons = int(
                        (json.loads(inv.read_text(encoding="utf-8")).get("stats") or {}).get(
                            "lessons"
                        )
                        or 0
                    )
                except Exception:
                    n_lessons = 0
            if not n_lessons and st.exists():
                try:
                    data = json.loads(st.read_text(encoding="utf-8"))
                    n_lessons = sum(
                        len(c.get("lessons") or []) for c in (data.get("chapters") or [])
                    )
                except Exception:
                    n_lessons = 0
            if not n_lessons:
                # count description.md in dump
                try:
                    n_lessons = len(list(root.rglob("description.md")))
                except Exception:
                    n_lessons = 0
        if n_locales is None:
            try:
                import config as Cfg

                n_locales = max(1, len(Cfg.get_course_locales() or []))
            except Exception:
                n_locales = 10
    n_lessons = int(n_lessons or 0)
    n_locales = int(n_locales or 10)
    task_ids = tasks or list(LLM_TASKS.keys())
    rows = []
    total = 0.0
    for tid in task_ids:
        meta = LLM_TASKS.get(tid) or {}
        cfg = get_task_llm(tid)
        model = cfg.get("model") or DEFAULT_PRIMARY_MODEL
        pin, pout = pricing_for_model(model)
        # tokens
        tin = float(meta.get("est_in_course") or 0)
        tout = float(meta.get("est_out_course") or 0)
        tin += float(meta.get("est_in_per_lesson") or 0) * n_lessons
        tout += float(meta.get("est_out_per_lesson") or 0) * n_lessons
        mult = float(meta.get("locale_multiplier") or 1)
        if tid == "localize":
            mult = float(n_locales)
        tin *= mult
        tout *= mult
        cost = tin * pin + tout * pout
        # also estimate fallback path if primary fails (50% contingency optional) — show both
        fmodel = cfg.get("fallback_model") or DEFAULT_FALLBACK_MODEL
        fpin, fpout = pricing_for_model(fmodel)
        fcost = tin * fpin + tout * fpout
        rows.append(
            {
                "task": tid,
                "title": cfg.get("title") or meta.get("title") or tid,
                "provider": cfg.get("provider"),
                "model": model,
                "fallback_model": fmodel,
                "tokens_in": int(tin),
                "tokens_out": int(tout),
                "usd_primary": round(cost, 4),
                "usd_if_fallback": round(fcost, 4),
                "lessons": n_lessons,
                "locales": n_locales if tid == "localize" else 1,
            }
        )
        total += cost
    return {
        "course": course_name,
        "lessons": n_lessons,
        "locales": n_locales,
        "rows": rows,
        "usd_total_primary": round(total, 4),
        "usd_total_if_all_fallback": round(sum(r["usd_if_fallback"] for r in rows), 4),
        "note": (
            "Ước lượng thô theo token/bài × giá OpenRouter (USD/token). "
            "Thực tế phụ thuộc độ dài transcript, số locale, cache, provider routing."
        ),
        "rankings_url": "https://openrouter.ai/rankings#leaderboard-table",
    }


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

    models = list(meta.get("models") or [model])
    if pid == "openrouter":
        # merge ranked catalog
        for mid in openrouter_model_choices():
            if mid not in models:
                models.append(mid)
    return {
        "id": pid,
        "title": meta.get("title") or pid,
        "kind": meta.get("kind") or "openai",
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "models": models,
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
        headers["X-Title"] = "Skool Downloader"
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
