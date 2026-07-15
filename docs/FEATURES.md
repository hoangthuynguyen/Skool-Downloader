# Skool Downloader — Danh sách tính năng

> Phiên bản: **3.3.0** (`course-os-complete`) · `python app/main.py --version`  

---

## 0x. OpenRouter LLM hub (3.3.0) — model theo tính năng + cost

| Mục | Chi tiết |
|-----|----------|
| Default primary | `deepseek/deepseek-v4-flash` (DeepSeek V4 Flash) |
| Default fallback | `xiaomi/mimo-v2.5` (MiMo-V2.5) |
| API | Dán **OpenRouter** key trên **Xuất & Báo cáo** (hoặc provider riêng) |
| Per-task routing | research · structure · summary · assets · localize · translate · image_gen · video_gen · qa · prompt |
| Rankings refresh | Nút **↻ Rankings** → `openrouter.ai/api/v1/models` (xem [leaderboard](https://openrouter.ai/rankings#leaderboard-table)) |
| Cost estimate | Nút **Tính chi phí khóa** → `$` theo model × số bài (lưu `_llm_cost_estimate.md`) |

Catalog ranking (gợi ý): Hy3 free · MiMo-V2.5 · DeepSeek V4 Flash · MiniMax M3 · GLM 5.2 · Nemotron 3 Ultra free · DeepSeek V4 Pro · Claude Opus 4.8/4.7 · Step 3.7 Flash · Sonnet 4.6/5 · Gemini 3 Flash · GPT-5.5 · MiMo-V2.5-Pro · Gemini 2.5 Flash/Lite · Laguna M.1 free · Gemini 3.1 Flash Lite · gpt-oss-120b.

---

## 0y. OmniVoice TTS (3.2.0) — text → speech local (Mac MPS)

| Module | Việc | GUI / CLI |
|--------|------|-----------|
| `course_omnivoice.py` | Clone giọng `ref.wav` → `tts_omnivoice.wav` | **🎙️ OmniVoice TTS** |
| Toggle | **Mặc định TẮT** · `tts_flag.json` per lesson | `on-all` / `off-all` / board / `one …` |
| Streamlit | `~/Downloads/omni_app.py` (Cloning + Design) | `ui` hoặc `streamlit run` |
| Video lab | provider `omnivoice` trong run-queue | Video lab → omnivoice |

```bash
# UI Streamlit
conda activate omnivoice
export STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
streamlit run ~/Downloads/omni_app.py

# Course OS
python app/course_omnivoice.py --course "X" --enable-all
python app/course_omnivoice.py --course "X" --lesson "01 - Chap/01 - Lesson"
python app/course_omnivoice.py --course "X" --all --limit 3
python app/course_omnivoice.py --course "X" --disable-all
python app/course_video.py --course "X" --prepare --provider omnivoice --run-queue --limit 2
```

Env: conda `omnivoice` · ref: `~/Downloads/ref.wav`

---

## 0z. COMPLETE (3.0.0) — finish-all · registry · tests

| Module | Việc |
|--------|------|
| `course_finish.py` | **Hoàn tất mọi bước còn thiếu** (core + GTM ship pack) |
| `course_features.py` | Feature registry — verify 21 modules import/API |
| `tests_course_os.py` | Unit smoke (pptx/thumbs/board/ops/finish dry-run) |
| Status mở rộng | + slides/pptx/thumbs/portal/notion/ops trong % complete |
| GUI **🚀 FINISH ALL** | Dry-run plan hoặc chạy thật |
| Selftest | Gồm `course_features` (+ full tests khi không `--quick`) |

```bash
# Plan còn thiếu
python app/course_finish.py --course "X" --dry-run

# Chạy hết (local video prepare, có thể skip localize)
python app/course_finish.py --course "X" --finish --provider local
python app/course_finish.py --course "X" --finish --skip-localize

# Chỉ GTM pack (đã có assets)
python app/course_finish.py --course "X" --ship-only

# Verify all feature modules
python app/course_features.py --write
python app/tests_course_os.py
python app/selftest.py
```

### External (cần credentials — không auto)

| Việc | Cách |
|------|------|
| YouTube upload thật | `_publish/youtube_season/upload_drafts_HELPER.py` + OAuth |
| Avatar HeyGen/Synthesia | Media keys + `course_video --run-queue` |
| Post Skool live | `_publish/skool_clipboard/clipboard.html` |
| Whisper STT | `pip install faster-whisper` |

---

## 0i. Board DnD · competitor · Notion (2.28)

| Module | Việc | CLI / GUI |
|--------|------|-----------|
| `course_board --html` | **Drag-and-drop** reorder lessons + chapters | GUI Board · Download/Copy JSON |
| `course_competitor.py` | Market/course scan + optional LLM gap | **🕵️ Competitor scan** |
| `course_notion.py` | Notion MD pack + webhook notify | **📓 Notion + Webhook** |
| Wizard finish | Auto `_course_status` + webhook nếu cấu hình | env `COURSE_OS_WEBHOOK` / settings |

```bash
python app/course_board.py --course "X" --html
python app/course_competitor.py --course "X" --llm
python app/course_notion.py --course "X" --export
python app/course_notion.py --course "X" --set-webhook "https://hooks.slack.com/..."
python app/course_notion.py --course "X" --export --webhook "$COURSE_OS_WEBHOOK"
```

---

## 0h. Course OS portfolio & GTM+ (2.27)

| Module | Việc | CLI / GUI |
|--------|------|-----------|
| `course_portfolio.py` | Multi-course % complete | **🗂 Portfolio** → `_course_portfolio.html` |
| `course_board --html` | Board HTML edit + download JSON | **📐 Board** → `html` · `--import-json` |
| `course_portal.py` | Student portal tĩnh + quiz + progress | **🎓 Student portal** |
| `course_ab.py` | A/B titles & hooks | **🧪 A/B titles** |
| `course_video --preview-voice` | Nghe voice trước full render | **🔊 Voice preview** |
| `course_review --render-approved` | Approve locale → TTS/video queue | review `render` |
| Locale glossary | `locale_terms` per language | `course_ops --glossary-locale es A B` |
| RTL slides | `dir=rtl` cho ar/he | `course_slides` |

```bash
python app/course_portfolio.py --html
python app/course_board.py --course "X" --html
python app/course_board.py --course "X" --import-json ~/Downloads/_upgrade_new_structure.json
python app/course_portal.py --course "X" --open
python app/course_ab.py --course "X"
python app/course_video.py --course "X" --preview-voice --provider local
python app/course_review.py --course "X" --render-approved --locale es --provider local --limit 2
python app/course_ops.py --course "X" --glossary-locale es "Workshop" "Taller"
```

---

## 0g. Course OS ship pack (2.26) — PPTX · thumbs · incremental · GTM

| Module | Việc | CLI / GUI |
|--------|------|-----------|
| `course_pptx.py` | PowerPoint pure OOXML (không cần python-pptx) | GUI **📑 PPTX + Thumbs** → `_pptx/` |
| `course_thumbs.py` | Cover PNG 1280×720 (PIL) | `_thumbnails/` + `thumbnail.png`/bài |
| `course_review --side-by-side` | HTML master vs locale 2 cột | GUI review → `side` |
| `course_incremental.py` | Scan obsolete + regen missing only | GUI **⚡ Incremental** · schedule mặc định |
| `course_ops --cost-dashboard` | LLM spent + video est | GUI **💰 Cost dashboard** |
| `course_qa --eval-golden` | Baseline + delta score | `--save-baseline` |
| Skool clipboard | Copy-paste HTML + ALL_POSTS.md | `course_publish --clipboard` |
| Sales HTML | Landing tĩnh | `--sales-html` |
| YouTube helper | `upload_drafts_HELPER.py` + OAuth README | trong `_publish/youtube_season/` |

```bash
python app/course_pptx.py --course "X"
python app/course_thumbs.py --course "X"
python app/course_review.py --course "X" --side-by-side --filter pending
python app/course_incremental.py --course "X" --run --research-quick
python app/course_ops.py --course "X" --cost-dashboard
python app/course_qa.py --course "X" --eval-golden --save-baseline
python app/course_publish.py --course "X" --clipboard --sales-html
```

---

## 0f. Course OS completion (2.25) — status · slides · ops · gates

| Module | Việc | CLI / GUI |
|--------|------|-----------|
| `course_status.py` | Checklist pipeline + gợi ý bước tiếp | `--md` · GUI **📊 Pipeline status** |
| `course_slides.py` | `slide_outline.md` → HTML deck (←/→) | GUI **🖼 Slides HTML** → `_slides/` |
| `course_ops.py` CLI | Glossary term-lock · style · budget cap · version bump | `--init` `--glossary-add` `--budget-cap` |
| Budget gate | Chặn LLM khi vượt `$` cap/khóa | tự trong `_llm` · `course_ops --budget-show` |
| Review loop | Re-localize rejected · bulk approve | `course_review --relocalize-rejected` |
| Media keys GUI | Lưu ElevenLabs/HeyGen/Synthesia | GUI **🔑 Media API keys** |
| Windows schedule | `schtasks` re-upgrade | `course_schedule --install` (win32) |

```bash
python app/course_status.py --course "X" --md
python app/course_slides.py --course "X" --open
python app/course_ops.py --course "X" --init
python app/course_ops.py --course "X" --budget-cap 40
python app/course_ops.py --course "X" --glossary-add "Claude"
python app/course_review.py --course "X" --relocalize-rejected
python app/course_review.py --course "X" --approve-all-pending
```

---

## 0e. Course OS ops (2.24) — render · review · schedule · board

| Module | Việc | CLI / GUI |
|--------|------|-----------|
| `course_video.py` | **Real render queue**: ElevenLabs TTS, HeyGen, Synthesia, local `say` | `--prepare --run-queue --provider …` · GUI **🎥 Video lab** |
| | Voice-per-locale (`_brand_kit.json` → `locale_voices`) | `--locale ja` · `--set-voice ja VOICE_ID` · `--set-key elevenlabs sk_…` |
| `course_review.py` | Human review queue cho locales | `--build` / `--approve` / `--reject` / `--export-pending` · GUI **👀 Locale review** |
| `course_schedule.py` | Re-upgrade định kỳ (launchd macOS / cron) | `--install --interval weekly` · GUI **🗓 Schedule** |
| `course_board.py` | Curriculum board (edit structure JSON) | `--show` / `--add-chapter` / `--add-lesson` · GUI **📐 Board** |
| Selective localize | Chỉ dịch bài khớp substring | `course_studio.py --localize --only Intro --only MCP` |
| Official docs crawl | Research fetch docs/changelog tool | tự chạy trong `--research` (web bật) |

```bash
# Video: prepare + render 2 jobs (cần key hoặc --provider local)
python app/course_video.py --course "X" --prepare --provider elevenlabs --run-queue --limit 2
python app/course_video.py --course "X" --prepare --locale es --provider elevenlabs
python app/course_video.py --course "X" --set-voice ja YOUR_ELEVEN_VOICE_ID

# Locale review
python app/course_review.py --course "X" --build
python app/course_review.py --course "X" --export-pending
python app/course_review.py --course "X" --approve es "01 - C/01 - L" --note ok

# Schedule + board
python app/course_schedule.py --course "X" --install --interval weekly
python app/course_board.py --course "X" --show
python app/course_board.py --course "X" --add-chapter "AI Agents 2026"

# Selective localize
python app/course_studio.py --course "X" --localize --locales "es,ja" --only Intro --only Agents
```

---

## 0d. Course OS — phần “còn thiếu” đã bổ sung (2.23)

| Module | Việc |
|--------|------|
| **Course Studio (GUI nav)** | Wizard FULL + bước lẻ |
| `course_wizard.py` | inventory→research→structure→assets→video→localize→publish→version |
| `course_video.py` | captions/SRT/VTT/SSML + cost estimate + `_video_queue.json` |
| `course_publish.py` | Skool export, YouTube TSV, email nurture, lead magnets, sales pack, zip+license |
| `course_qa.py` | loc QA, structure diff, eval sample, fact-check LLM |
| `course_ops.py` | glossary/term-lock, style guide, TM, research cache 7d, budget, obsolescence, versioning |
| Approve research | `_upgrade_research_approved.json` + `--require-approve` |
| Research depth | `quick` / `standard` / `deep` |
| Regen 1 bài | `course_studio.py --regen "Tên bài"` |

```bash
python app/course_wizard.py --course "X" --full --depth standard --lang vi
python app/course_wizard.py --course "X" --approve-research
python app/course_video.py --course "X" --prepare
python app/course_publish.py --course "X" --all
python app/course_qa.py --course "X" --all
```

---

## 0c. Course Studio (Asset pack → Master lang → Locale hub)

| # | Tính năng | Mặc định | CLI / GUI |
|---|-----------|----------|-----------|
| 1 | **Lesson Asset Pack** | BẬT khi generate lessons | `course_studio.py --assets` · GUI **🎬 Asset pack** |
| | `lesson.md` · `talking_script.md` · `workshop.md` · `use_cases.md` · `resources.md` · `broll_cues.md` · `slide_outline.md` · `summary.md` · `quiz.json` | | trong `_upgrade_v2/` |
| 2 | **Master language** | `vi` (hoặc `en`) | `--lang en` · settings `course_master_lang` |
| 3 | **Locale hub** | 12 locale T1 | `--localize --locales "zh-CN,ja,ko,es…"` · GUI **🌍 Localize** |
| | Catalog ~40 ngôn ngữ thương mại (`--list-locales`) | | output `_upgrade_v2/locales/<code>/` |

```bash
# 1) Sau khi có structure
python app/course_studio.py --course "X" --assets --lang vi

# 2) Master EN
python app/course_studio.py --course "X" --assets --lang en

# 3) Localize
python app/course_studio.py --course "X" --localize --locales "zh-CN,ja,ko,es,pt-BR,id,hi,fr,de,ar"

# Full pack
python app/course_studio.py --course "X" --full-pack --lang vi
```
> Hướng dẫn dùng chi tiết: [../README.md](../README.md) · Workflows: [HUONG_DAN_FEATURES_WORKFLOWS.md](HUONG_DAN_FEATURES_WORKFLOWS.md)

---

## 0b. Nâng cấp khóa học (market research → curriculum mới)

| # | Bước | Output | Bật/tắt |
|---|------|--------|---------|
| **0** | **Questionnaire mong muốn user** (11 câu) | `_upgrade_questionnaire.json` + `_Upgrade_Questionnaire.md` | **`course_upgrade_questionnaire`** (mặc định **BẬT**) |
| 1 | Inventory khóa local | `_upgrade_inventory.json` | luôn |
| 2 | Nghiên cứu thị trường (tool/tính năng mới) | web snippets + LLM | **`course_upgrade_research`** (mặc định BẬT) |
| 3 | Web snippets (DuckDuckGo HTML) | trong research JSON | **`course_upgrade_web`** (mặc định BẬT) |
| 4 | Báo cáo toàn diện | `_Upgrade_Research_Report.md` + **`.docx`** | sau research |
| 5 | User bổ sung | `_Upgrade_User_Notes.md` | tay |
| 6 | LLM sinh cấu trúc khóa mới (loại bài cũ) | `_upgrade_new_structure.json` + `_Upgrade_New_Structure.md` | DeepSeek→Gemini |
| 7 | (Tuỳ chọn) Sinh outline từng bài | folder `_upgrade_v2/` | `--generate-lessons` / `--full` |

**as_of** = ngày chạy phần mềm (`date.today()`).

```bash
python app/course_upgrade.py --course "TenKhoa" --research
python app/course_upgrade.py --course "X" --no-questionnaire
python app/course_upgrade.py --course "X" --interactive-questions --research
python app/course_upgrade.py --course "X" --answers-file answers.json --full
python app/course_upgrade.py --course "X" --structure-only   # sau khi sửa notes
```

GUI: **Xuất & Báo cáo** → **🔬 Nâng cấp khóa** → (mặc định) form câu hỏi → research → cấu trúc.

Câu hỏi gồm: đối tượng học, outcomes, giữ/loại bài, stack tool, tính năng mới, độ sâu, thời lượng, format, ràng buộc, ghi chú thêm.

---

## 0. Dashboard Quick Run (URL khóa)

| # | Tính năng | Mặc định | Tắt/bật |
|---|-----------|----------|---------|
| 0.1 | **Ô URL khóa** + nút **▶ Chạy** | — | Dán `https://www.skool.com/ten-khoa/classroom` |
| 0.2 | Mở browser → Classroom (login nếu cần) | — | Tự động |
| 0.3 | Dump **toàn bộ** chương → folder cấu trúc | — | Tự động sau khi lấy list |
| 0.4 | Tải video + extras | BẬT | Pipeline |
| 0.5 | Transcript auto-detect | **BẬT** | Tick / `--no-transcribe` |
| 0.6 | **Summary từng bài (VI)** | **BẬT** | Tick / `--no-lesson-summary` |
| 0.7 | **Thumbnail** ảnh bài | **BẬT** | Tick / settings `download_thumbnails` |
| 0.8 | **Links & resources** tham chiếu | **BẬT** | Tick / settings `fetch_resource_links` |
| 0.9 | LLM summary chính | **DeepSeek** `deepseek-chat` | Dashboard dropdown |
| 0.10 | LLM summary fallback | **Gemini** `gemini-2.0-flash` | Dashboard dropdown |

---

## 1. Pipeline lưu trữ khóa học

| # | Tính năng | Mô tả | Bật/tắt / CLI |
|---|-----------|--------|----------------|
| 1.1 | **Preflight** | Kiểm tra Python, Node, ffmpeg, yt-dlp, đĩa, JSON dump trước khi chạy | Tự chạy; `--skip-preflight` |
| 1.2 | **Tạo cây folder** | Mỗi chương/bài = 1 folder `NN - Tên` | `folders` / pipeline |
| 1.3 | **Mô tả + resources** | `description.md`, `lesson.json`, `links.md`, `resources/` | `extras` |
| 1.4 | **Tải video** | Native Skool → Loom/YouTube; resume; phân loại lỗi | `videos` · `--only videos` |
| 1.5 | **Two-pass video** | Ưu tiên native (token 24h) rồi nền tảng ngoài | Tự động trong pipeline |
| 1.6 | **Until-clean** | Lặp tải đến khi hết bài recoverable (rate-limit…) | GUI tick / `--until-clean` |
| 1.7 | **Tải theo chương/bài** | Chỉ một chương hoặc một lesson path | `--chapter` · `--lesson` · GUI |
| 1.8 | **Retry failed** | Chỉ tải lại `video_fails.json` | `--retry-failed` · `--fail-codes` |
| 1.9 | **Missing-only / smart-update** | Chỉ bài thiếu; ưu tiên chương mới | `--missing-only` · `--smart-update` |
| 1.10 | **Audit** | Đối chiếu JSON ↔ file → `video_audit.txt` | `audit` |
| 1.11 | **Workers song song** | 1–4 worker tải bài trong 1 khóa | `--workers N` · adaptive 429 |
| 1.12 | **Progress live** | Panel khóa / folder / video / bài + ETA | GUI + `_download_progress.json` |

---

## 2. Transcript & phụ đề (Whisper)

| # | Tính năng | Mô tả | Bật/tắt |
|---|-----------|--------|---------|
| 2.1 | **Auto transcript (mặc định BẬT)** | Sau khi tải video tự chạy faster-whisper | GUI tick · settings `auto_transcribe` · config `AUTO_TRANSCRIBE` |
| 2.2 | **Tắt transcript** | Không chạy Whisper khi tải | GUI **bỏ tick** · CLI `--no-transcribe` · settings `false` |
| 2.3 | **Ép transcript** | Chạy Whisper dù settings tắt | CLI `--transcribe` · `--only transcribe` |
| 2.4 | **Auto-detect ngôn ngữ** | Whisper tự nhận diện ngôn ngữ video (`WHISPER_LANG=auto`) | Đổi `WHISPER_LANG=en/vi/...` nếu muốn cố định |
| 2.5 | **Giới thiệu bài** | Gộp `description.md` vào plain text transcript | `TRANSCRIPT_INCLUDE_INTRO=True` |
| 2.6 | **File từng bài** | `video.txt` (intro + transcript) + `video.srt` + `video.lang` | Cùng folder với `video.mp4` |
| 2.7 | **All transcript** | `all transcript.txt` gộp mọi bài theo thứ tự, cách 3 dòng trống | Gốc khóa học |
| 2.8 | **Resume phụ đề** | Bỏ qua bài đã có `video.txt`; `.notranscribe` nếu không audio | Tự động |
| 2.9 | **Watcher nền** | Quét video mới → transcript (Windows task / CLI) | `transcribe_watch.py` · GUI Phụ đề |
| 2.10 | **Model** | Mặc định `distil-large-v3` (faster-whisper) | `WHISPER_MODEL` · `WHISPER_COMPUTE` |

### Cấu trúc plain text mỗi bài (`video.txt`)

```text
## Giới thiệu bài

…nội dung description.md…

## Transcript (ngôn ngữ: vi)

…lời thoại Whisper (auto-detect)…
```

### File tổng hợp

```text
courses/<Tên khóa>/all transcript.txt
```

---

## 3. Giao diện (GUI)

| # | Màn / vùng | Tính năng |
|---|------------|-----------|
| 3.1 | **Dashboard** | KPI khóa, chọn BASE, card khóa, progress live, bookmark |
| 3.2 | **Thêm / mở khóa** | Wizard dump browser + tải |
| 3.3 | **Trình tải (Manager)** | Cây chương/bài, tải all/chương/bài, fail panel, smart update |
| 3.4 | **Dump browser** | Playwright + storage_state: list chương, dump JSON trong app |
| 3.5 | **Cứu native** | Phát hiện JWT hết hạn → re-dump token → tải lại |
| 3.6 | **Phụ đề** | Chạy lại transcript thiếu; link dịch VI |
| 3.7 | **Xuất & Báo cáo** | Word, dịch, tóm tắt AI, LLM Prompt multi-provider |
| 3.8 | **Hàng đợi** | Multi-course queue, workers, pause/resume |
| 3.9 | **Cập nhật v2** | Diff chương mới / bài thiếu / native expired |
| 3.10 | **Cloud** | R2 / Google Drive / OneDrive; sync sau tải |
| 3.11 | **Chat RAG** | Hỏi nội dung khóa (TF-IDF / dense) |
| 3.12 | **Tìm kiếm** | Transcript + mô tả + notes toàn kho |
| 3.13 | **Web Viewer** | Duyệt knowledge local (localhost) |
| 3.14 | **Health** | Lịch quét kho → `_health.json` |
| 3.15 | **Doctor / Env** | Kiểm tra tool, BASE, cài thiếu |
| 3.16 | **Dark / density** | Theme + compact/comfortable |
| 3.17 | **Discovery** | Cào catalog community Skool → SQLite/CSV |
| 3.18 | **Notes / favorites** | Ghi chú bài, bookmark, alias |
| 3.19 | **Notify** | Toast khi xong pipeline / sạch fail |

---

## 4. AI / LLM / học tập

| # | Tính năng | Module / CLI |
|---|-----------|--------------|
| 4.1 | Multi-LLM (Grok, Claude, OpenAI, Gemini, OpenRouter, Qwen, GLM, Kimi, DeepSeek) + fallback | `llm_providers.py` · `llm_prompt.py` |
| 4.2 | Prompt tùy chỉnh: dịch / rewrite / summary / glossary | GUI Xuất · CLI |
| 4.3 | Dịch tổng hợp + tóm tắt to-do (theo chương) | `ai_tools.py` · `report_bundle.py` |
| **4.3b** | **Summary từng bài (VI)** — Purpose, Summary 500/700/1000/1500 từ, Key takeaways, Todo step-by-step, Quotes, Resources | `lesson_summary.py` · GUI **Xuất & Báo cáo** · `summary.vi.md` + `_All_Summaries.vi.md` |
| 4.4 | RAG index + chat | `rag/` · `rag.chat` |
| 4.5 | Anki export (TSV cloze/blank) | `anki_export.py` |
| 4.6 | Offline quiz từ transcript | `quiz.py` |
| 4.7 | Learn playlist / study plan ICS | `learn_playlist.py` · `study_plan.py` |
| 4.8 | Content diff (mô tả/transcript đổi) | `content_diff.py` |
| 4.9 | Vault export (Obsidian / Notion MD) | `vault_export.py` |
| 4.10 | Knowledge pack backup/restore | `cloud/pack_backup.py` |

### 4.3b — Summary từng bài (chi tiết)

| Mục | Nội dung |
|-----|----------|
| **Input** | `description.md` + `video.txt` (+ notes/links nếu có) trong folder bài |
| **Output** | `summary.vi.md` cạnh video; gộp `_All_Summaries.vi.md` ở gốc khóa |
| **Ngôn ngữ** | Toàn bộ **tiếng Việt** |
| **Purpose** | Mục đích video |
| **Summary** | Ngắn ≈500 · TB ≈700 · Dài ≈1000 · Siêu dài ≈1500 từ (theo độ dài nguồn) |
| **Key takeaways** | Ý then chốt |
| **Todo list** | Checklist chi tiết, step-by-step |
| **Quotes** | Trích dẫn từ nguồn |
| **Resources** | Link/công cụ/file được nhắc |

```bash
python app/lesson_summary.py --course "TenKhoa"              # chỉ bài chưa có
python app/lesson_summary.py --course "X" --force            # ghi đè
python app/lesson_summary.py --course "X" --lesson "01 - A/02 - B"
python app/lesson_summary.py --course "X" --provider grok
```

---

## 5. Cloud & đồng bộ

| # | Provider | Ghi chú |
|---|----------|---------|
| 5.1 | Cloudflare R2 | `cloud.r2` · knowledge mode |
| 5.2 | Google Drive | OAuth · `cloud.gdrive` |
| 5.3 | OneDrive | MSAL · `cloud.onedrive` |
| 5.4 | Policy / skip | Không upload secrets · `cloud.policy` |
| 5.5 | Auto sync sau tải | Settings `cloud.after_download` |

---

## 6. Catalog communities (Excel / Discovery)

| # | Tính năng | Module |
|---|-----------|--------|
| 6.1 | Discovery scrape (lang/topic/price) | `discovery_scrape.py` · GUI Discovery |
| 6.2 | Cập nhật Excel catalog | `update_skool_xlsx.py` |
| 6.3 | Refresh members/price /about | `refresh_skool_xlsx_members.py` |
| 6.4 | Free cost = `$0` (tính doanh thu) | `save_excel` |
| 6.5 | Repair notes/cost | `--repair-notes` |

---

## 7. Vận hành & chất lượng

| # | Tính năng | CLI |
|---|-----------|-----|
| 7.1 | Doctor | `python app/doctor.py` · `--set-base` |
| 7.2 | Selftest | `python app/selftest.py` |
| 7.3 | Tools fix (yt-dlp, packages) | `tools_fix.py` |
| 7.4 | Cleanup `.part` / fails | `cleanup.py` |
| 7.5 | Disk report | `disk_report.py` |
| 7.6 | Health schedule | `health_check.py` · launchd/Task |
| 7.7 | Static site export | `export_site.py` |
| 7.8 | One-click launchers | `SkoolDownloader.cmd` / `.command` |
| 7.9 | Desktop shortcut | `install_shortcut.sh` / `.ps1` |
| 7.10 | Version history | `version.py` |

---

## 8. Cấu hình transcript quan trọng (`app/config.py` + `.settings.json`)

| Key | Mặc định | Ý nghĩa |
|-----|----------|---------|
| `AUTO_TRANSCRIBE` | `True` | Tự transcript sau tải |
| `auto_transcribe` (settings) | — | Ghi đè config (GUI tick) |
| `WHISPER_LANG` | `auto` | Auto-detect; hoặc `en` / `vi` |
| `WHISPER_MODEL` | `distil-large-v3` | Model faster-whisper |
| `TRANSCRIPT_INCLUDE_INTRO` | `True` | Gộp `description.md` |
| `ALL_TRANSCRIPT_NAME` | `all transcript.txt` | File tổng hợp gốc khóa |

### Tắt / bật nhanh

```bash
# Tắt lần này
python app/main.py --course "TenKhoa" --no-transcribe

# Bật ép (kể cả khi settings tắt)
python app/main.py --course "TenKhoa" --transcribe

# Chỉ transcript + all transcript.txt
python app/main.py --course "TenKhoa" --only transcribe --skip-preflight
```

GUI: màn **Tải khóa** → tick/bỏ tick  
*「Tự lấy transcript (faster-whisper, auto-detect ngôn ngữ + giới thiệu bài)」*.

---

## 9. Sơ đồ pipeline mặc định

```text
preflight
  → folders (cây chương/bài)
  → extras (description.md + resources)
  → videos (video.mp4)
  → transcribe  [nếu auto_transcribe]
        • auto-detect ngôn ngữ
        • video.txt = intro + transcript
        • video.srt
        • all transcript.txt (theo thứ tự bài)
  → audit
  → (tuỳ chọn) RAG index · notify · cloud sync
```
