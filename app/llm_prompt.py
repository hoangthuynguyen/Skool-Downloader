#!/usr/bin/env python3
"""
Sprint LLM — dich / cap nhat noi dung theo PROMPT tu chon (API LLM).

  python llm_prompt.py --course "X" --source tonghop --preset translate_vi
  python llm_prompt.py --course "X" --source tonghop --prompt "Dich sang tieng Viet..."
  python llm_prompt.py --course "X" --source lesson --lesson "01 - C/01 - L" --prompt "..."
  python llm_prompt.py --list-presets
  python llm_prompt.py --save-preset my_vi --prompt "..." --system "..."

Providers (multi + fallback):
  anthropic, openai, grok (xAI), openrouter, gemini, glm, qwen, deepseek,
  kimi (kiwi), siliconflow, doubao, stepfun, yi, baichuan, minimax, groq, custom
  See llm_providers.py · docs/HUONG_DAN_FEATURES_WORKFLOWS.md
"""
from __future__ import annotations

import argparse, json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import ai_tools as AI
import llm_providers as PROV

SETTINGS = AI.SETTINGS_FILE
CHUNK = 7000

# ---- Built-in presets (id -> {title, system, prompt, out_suffix}) ----
BUILTIN_PRESETS = {
    "translate_vi": {
        "title": "Dịch sang tiếng Việt",
        "system": (
            "Bạn là biên dịch viên chuyên nghiệp. Dịch sang TIẾNG VIỆT tự nhiên, dễ hiểu. "
            "GIỮ NGUYÊN định dạng Markdown (# tiêu đề, danh sách, **đậm**, liên kết, code). "
            "Không thêm lời bình — chỉ trả về bản dịch."
        ),
        "prompt": "Dịch toàn bộ nội dung sau sang tiếng Việt:\n\n{{content}}",
        "out_suffix": ".vi.md",
        "mode": "rewrite",
    },
    "translate_en": {
        "title": "Dịch sang tiếng Anh",
        "system": (
            "You are a professional translator. Translate into clear natural English. "
            "KEEP Markdown formatting. Output only the translation."
        ),
        "prompt": "Translate the following into English:\n\n{{content}}",
        "out_suffix": ".en.md",
        "mode": "rewrite",
    },
    "update_style": {
        "title": "Viết lại gọn, rõ (cập nhật style)",
        "system": (
            "Bạn là biên tập viên nội dung khóa học. Viết lại nội dung gọn, rõ, giữ ý chính. "
            "Giữ Markdown. Không bịa thêm thông tin không có trong nguồn."
        ),
        "prompt": (
            "Viết lại nội dung sau cho dễ đọc hơn (tiếng Việt nếu nguồn tiếng Việt, "
            "giữ ngôn ngữ gốc nếu không chắc):\n\n{{content}}"
        ),
        "out_suffix": ".updated.md",
        "mode": "rewrite",
    },
    "summary_todo": {
        "title": "Tóm tắt + To-do áp dụng",
        "system": (
            "Bạn là trợ lý đào tạo. Viết bằng TIẾNG VIỆT:\n"
            "1) Tóm tắt ý chính (gạch đầu dòng)\n"
            "2) To-do áp dụng cụ thể\n"
            "Ngắn gọn, Markdown."
        ),
        "prompt": "Tóm tắt và đưa to-do từ nội dung:\n\n{{content}}",
        "out_suffix": ".summary.md",
        "mode": "rewrite",
    },
    "extract_terms": {
        "title": "Trích thuật ngữ / glossary",
        "system": "Trích glossary thuật ngữ quan trọng. Markdown bảng: | Term | Giải thích |",
        "prompt": "Trích thuật ngữ từ:\n\n{{content}}",
        "out_suffix": ".glossary.md",
        "mode": "rewrite",
    },
    "custom": {
        "title": "Prompt tùy chỉnh (tự nhập)",
        "system": "Bạn là trợ lý AI hữu ích. Làm đúng yêu cầu người dùng. Ưu tiên Markdown.",
        "prompt": "{{user_prompt}}\n\n---\nNội dung nguồn:\n\n{{content}}",
        "out_suffix": ".llm.md",
        "mode": "rewrite",
    },
}

SOURCES = {
    "tonghop": "_TongHop.md",
    "tonghop_vi": "_TongHop.vi.md",
    "tomtat": "_TomTat.md",
    "notes": "_Notes_All.md",
    "lesson": None,  # can --lesson
    "file": None,    # can --file
}


def load_settings():
    return AI.load_settings()


def save_setting(key, value):
    AI.save_setting(key, value)


def get_provider() -> str:
    return PROV.get_provider()


def get_openai_config():
    """Legacy helper — map to openai provider config."""
    c = PROV.get_provider_config("openai")
    return {
        "api_key": c.get("api_key") or "",
        "base_url": c.get("base_url") or "https://api.openai.com/v1",
        "model": c.get("model") or "gpt-4o-mini",
    }


def llm_status():
    st = AI.status()
    ps = PROV.providers_status()
    oc = get_openai_config()
    return {
        **st,
        "provider": ps.get("provider"),
        "openai": bool(oc["api_key"]),
        "openai_model": oc["model"],
        "openai_base": oc["base_url"],
        "ready": bool(ps.get("ready")),
        "ready_count": ps.get("ready_count"),
        "fallback": ps.get("fallback"),
        "providers": ps.get("providers"),
    }


def user_presets() -> dict:
    s = load_settings()
    p = s.get("llm_presets") or {}
    return p if isinstance(p, dict) else {}


def save_user_preset(pid: str, title: str, system: str, prompt: str,
                     out_suffix=".llm.md", mode="rewrite"):
    pid = re.sub(r"[^a-zA-Z0-9_\-]", "_", (pid or "custom").strip()) or "custom"
    s = load_settings()
    presets = dict(s.get("llm_presets") or {})
    presets[pid] = {
        "title": title or pid,
        "system": system or "",
        "prompt": prompt or "{{content}}",
        "out_suffix": out_suffix or ".llm.md",
        "mode": mode or "rewrite",
        "user": True,
    }
    s["llm_presets"] = presets
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return pid


def list_presets() -> dict:
    """Builtin + user presets."""
    out = {k: dict(v) for k, v in BUILTIN_PRESETS.items()}
    for k, v in user_presets().items():
        out[k] = dict(v)
        out[k]["user"] = True
    return out


def get_preset(pid: str) -> dict | None:
    if not pid:
        return None
    if pid in BUILTIN_PRESETS:
        return dict(BUILTIN_PRESETS[pid])
    return user_presets().get(pid)


def llm_complete(system: str, user_text: str, provider=None, max_tokens=8000,
                 model=None, fallback=True, log=print):
    """Goi LLM multi-provider + fallback. Tra ve text."""
    text, used = PROV.complete_with_fallback(
        system, user_text,
        provider=provider,
        fallback=fallback,
        max_tokens=max_tokens,
        model=model,
        log=log,
    )
    return text


def render_prompt(template: str, content: str, user_prompt: str = "", **extra) -> str:
    """Thay {{content}}, {{user_prompt}}, {{course}}, ..."""
    t = template or "{{content}}"
    # Neu user_prompt va template khong co placeholder, ghep o dau
    if user_prompt and "{{user_prompt}}" not in t and "{{content}}" in t:
        t = "{{user_prompt}}\n\n" + t
    elif user_prompt and "{{user_prompt}}" not in t and "{{content}}" not in t:
        t = "{{user_prompt}}\n\n{{content}}"
    mapping = {
        "content": content or "",
        "user_prompt": user_prompt or "",
        **{k: str(v) for k, v in (extra or {}).items()},
    }
    out = t
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    # neu van con {{content}} rong
    if "{{content}}" in out:
        out = out.replace("{{content}}", content or "")
    return out


def load_source(root, source="tonghop", lesson=None, file_path=None, log=print):
    """Tra ve (text, suggested_out_stem, meta)."""
    root = Path(root)
    source = (source or "tonghop").lower()
    meta = {"source": source, "root": str(root)}

    if source == "file" and file_path:
        p = Path(file_path)
        if not p.is_file():
            p = root / file_path
        text = p.read_text(encoding="utf-8", errors="replace")
        return text, p.stem, {**meta, "path": str(p)}

    if source == "lesson":
        if not lesson:
            raise ValueError("source=lesson cần --lesson (rel path)")
        folder = Path(lesson)
        if not folder.is_dir():
            folder = root / lesson
        if not folder.is_dir():
            raise FileNotFoundError(lesson)
        parts = []
        for name in ("description.md", "video.txt", "notes.md"):
            f = folder / name
            if f.is_file():
                parts.append(f"# {name}\n\n" + f.read_text(encoding="utf-8", errors="replace"))
        if not parts:
            raise FileNotFoundError(f"Không có description/transcript/notes trong {folder}")
        return "\n\n".join(parts), folder.name, {**meta, "path": str(folder)}

    if source == "notes":
        try:
            import notes as N
            N.export_notes_md(root)
        except Exception as e:
            log(f"[notes export] {e}")
        p = root / "_Notes_All.md"
        if not p.exists():
            raise FileNotFoundError("Chưa có notes — ghi ✎ vài bài trước")
        return p.read_text(encoding="utf-8", errors="replace"), "_Notes_All", {**meta, "path": str(p)}

    # tonghop / tomtat / tonghop_vi
    name = SOURCES.get(source) or "_TongHop.md"
    p = root / name
    if source in ("tonghop",) and not p.exists():
        log("Chưa có _TongHop.md → đang gộp…")
        import export as E
        E.run(root=root)
    if not p.exists():
        raise FileNotFoundError(f"Không thấy {p}")
    return p.read_text(encoding="utf-8", errors="replace"), p.stem, {**meta, "path": str(p)}


def run_prompt(
    root,
    *,
    source="tonghop",
    lesson=None,
    file_path=None,
    preset=None,
    system=None,
    prompt=None,
    user_prompt="",
    out_path=None,
    out_suffix=None,
    provider=None,
    model=None,
    fallback=True,
    max_chars=None,
    log=print,
):
    """
    Chay LLM theo prompt.
    - preset: id builtin/user
    - system/prompt: override
    - user_prompt: text them vao {{user_prompt}} (cho preset custom)
    - provider/model/fallback: multi-provider
    """
    root = Path(root)
    st = llm_status()
    if not st["ready"]:
        raise RuntimeError(
            "Chưa có LLM API key. Cấu hình Claude / OpenAI / Gemini / OpenRouter / "
            "Qwen / GLM / Kimi / DeepSeek… trong Xuất & Báo cáo."
        )

    preset_data = get_preset(preset) if preset else None
    system = system if system is not None else (preset_data or {}).get("system") or ""
    prompt_tpl = prompt if prompt is not None else (preset_data or {}).get("prompt")
    if not prompt_tpl:
        # freeform: user_prompt only
        if user_prompt:
            prompt_tpl = "{{user_prompt}}\n\n---\nNội dung nguồn:\n\n{{content}}"
            system = system or BUILTIN_PRESETS["custom"]["system"]
        else:
            raise ValueError("Cần --preset hoặc --prompt hoặc --user-prompt")

    suffix = out_suffix or (preset_data or {}).get("out_suffix") or ".llm.md"
    content, stem, meta = load_source(
        root, source=source, lesson=lesson, file_path=file_path, log=log
    )
    if max_chars and len(content) > max_chars:
        log(f"   cắt content {len(content)} → {max_chars} ký tự")
        content = content[:max_chars]

    course_name = C.COURSE or root.name
    parts_out = []
    used_providers = []
    cs = AI.chunks(content, CHUNK) if content else [""]
    log(f">> LLM [{provider or get_provider()}] fallback={fallback} source={source} chunks={len(cs)}")
    for i, chunk in enumerate(cs, 1):
        if len(cs) > 1:
            log(f"   chunk {i}/{len(cs)}…")
        filled = render_prompt(
            prompt_tpl,
            content=chunk,
            user_prompt=user_prompt,
            course=course_name,
            source=source,
            chunk=f"{i}/{len(cs)}",
        )
        text, used = PROV.complete_with_fallback(
            system, filled,
            provider=provider,
            fallback=fallback,
            model=model,
            log=log,
        )
        used_providers.append(used)
        parts_out.append(text)

    result = "\n\n".join(parts_out).strip() + "\n"
    used_main = used_providers[0] if used_providers else (provider or get_provider())

    if out_path:
        out = Path(out_path)
    else:
        suf = suffix if str(suffix).startswith(".") else f".{suffix}"
        if not suf.endswith((".md", ".txt", ".json")):
            suf = suf + ".md"
        out = root / f"{stem}{suf}"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # header meta
    header = (
        f"<!-- llm_prompt: preset={preset or 'custom'} provider={used_main} "
        f"source={source} at={time.strftime('%Y-%m-%dT%H:%M:%S')} -->\n\n"
    )
    out.write_text(header + result, encoding="utf-8")
    log(f">> Đã ghi: {out} ({len(result)} chars) via {used_main}")
    return {
        "path": str(out),
        "chars": len(result),
        "preset": preset,
        "source": source,
        "provider": used_main,
        "providers_used": used_providers,
        "chunks": len(cs),
    }


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="LLM custom prompt — dịch / cập nhật nội dung")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--source", default="tonghop",
                    help="tonghop|tonghop_vi|tomtat|notes|lesson|file")
    ap.add_argument("--lesson", help="Rel path bai (khi source=lesson)")
    ap.add_argument("--file", help="File path (khi source=file)")
    ap.add_argument("--preset", help="Id preset (translate_vi, custom, ...)")
    ap.add_argument("--prompt", help="Template prompt (co the dung {{content}} {{user_prompt}})")
    ap.add_argument("--user-prompt", default="", help="Yeu cau tu do cua ban")
    ap.add_argument("--system", help="System prompt override")
    ap.add_argument("--out", help="Duong dan file output")
    ap.add_argument("--out-suffix", help="vd .vi.md")
    ap.add_argument("--provider", help="anthropic|openai|openrouter|gemini|glm|qwen|deepseek|kimi|…")
    ap.add_argument("--model", help="Override model id")
    ap.add_argument("--no-fallback", action="store_true", help="Khong thu provider khac khi loi")
    ap.add_argument("--max-chars", type=int, default=None)
    ap.add_argument("--list-presets", action="store_true")
    ap.add_argument("--list-providers", action="store_true")
    ap.add_argument("--save-preset", metavar="ID", help="Luu preset user")
    ap.add_argument("--title", default="", help="Tieu de khi --save-preset")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--set-provider", help="Dat provider mac dinh")
    ap.add_argument("--set-key", nargs=2, metavar=("PROVIDER", "KEY"), help="Luu API key cho provider")
    ap.add_argument("--set-model", nargs=2, metavar=("PROVIDER", "MODEL"))
    ap.add_argument("--set-base", nargs=2, metavar=("PROVIDER", "URL"))
    ap.add_argument("--set-fallback", help="Chuoi fallback, vd: openrouter,gemini,qwen,glm,kimi")
    ap.add_argument("--set-openai-key", help="(legacy) openai key")
    ap.add_argument("--set-openai-base", help="(legacy)")
    ap.add_argument("--set-openai-model", help="(legacy)")
    a = ap.parse_args()

    if a.set_provider:
        PROV.set_provider(a.set_provider)
        print("llm_provider =", PROV.get_provider())
    if a.set_fallback:
        print("fallback =", PROV.set_fallback_chain(a.set_fallback))
    if a.set_key:
        PROV.save_provider_config(a.set_key[0], api_key=a.set_key[1])
        print("saved key for", PROV.normalize_provider(a.set_key[0]))
    if a.set_model:
        PROV.save_provider_config(a.set_model[0], model=a.set_model[1])
        print("saved model for", a.set_model[0], "=", a.set_model[1])
    if a.set_base:
        PROV.save_provider_config(a.set_base[0], base_url=a.set_base[1])
        print("saved base for", a.set_base[0])
    if a.set_openai_key is not None:
        PROV.save_provider_config("openai", api_key=a.set_openai_key.strip())
        print("openai_api_key saved")
    if a.set_openai_base:
        PROV.save_provider_config("openai", base_url=a.set_openai_base.strip())
    if a.set_openai_model:
        PROV.save_provider_config("openai", model=a.set_openai_model.strip())

    if a.list_providers:
        for r in PROV.providers_status()["providers"]:
            mark = "✓" if r["configured"] else "·"
            print(f"  {mark} {r['id']:14} {r['title'][:28]:28} model={r['model']}")
        print("fallback:", ", ".join(PROV.get_fallback_chain()))
        return

    if a.check or a.set_provider or a.set_key or a.set_openai_key is not None:
        print(json.dumps(llm_status(), ensure_ascii=False, indent=2))
        if a.check or not (a.preset or a.prompt or a.user_prompt or a.save_preset or a.list_presets):
            if a.check:
                return

    if a.list_presets:
        for pid, p in list_presets().items():
            tag = " [user]" if p.get("user") else ""
            print(f"  {pid:20} {p.get('title', '')}{tag}")
        return

    if a.save_preset:
        if not (a.prompt or a.user_prompt):
            ap.error("--save-preset can --prompt hoac --user-prompt")
        pid = save_user_preset(
            a.save_preset,
            title=a.title or a.save_preset,
            system=a.system or BUILTIN_PRESETS["custom"]["system"],
            prompt=a.prompt or "{{user_prompt}}\n\n{{content}}",
            out_suffix=a.out_suffix or ".llm.md",
        )
        print("saved preset:", pid)
        return

    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)

    if not (a.preset or a.prompt or a.user_prompt):
        ap.error("Can --preset / --prompt / --user-prompt (hoac --list-presets / --check / --list-providers)")

    r = run_prompt(
        C.ROOT,
        source=a.source,
        lesson=a.lesson,
        file_path=a.file,
        preset=a.preset,
        system=a.system,
        prompt=a.prompt,
        user_prompt=a.user_prompt,
        out_path=a.out,
        out_suffix=a.out_suffix,
        provider=a.provider,
        model=a.model,
        fallback=not a.no_fallback,
        max_chars=a.max_chars,
    )
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
