# Skool Downloader

Công cụ lưu trữ **toàn bộ một khóa học Skool** về máy: cây thư mục theo chương/bài, video (native Skool + Loom + YouTube), mô tả bài, tài liệu (resources) và **transcript plain text (faster-whisper, auto-detect ngôn ngữ)** — chạy bằng **một lệnh** hoặc GUI 1 click.

> **Phiên bản:** **3.2.2** (`course-os-complete`) · `python app/main.py --version`  
> **Danh sách tính năng đầy đủ:** **[docs/FEATURES.md](docs/FEATURES.md)**  
> **Workflows / LLM / phím tắt:** **[docs/HUONG_DAN_FEATURES_WORKFLOWS.md](docs/HUONG_DAN_FEATURES_WORKFLOWS.md)**

---

## Mục lục

1. [Mở app](#0-mở-app-1-click)
2. [Cách dùng nhanh](#1-cách-dùng-nhanh-khuyến-nghị)
3. [Transcript (mặc định BẬT)](#2-transcript--phụ-đề)
4. [Pipeline & cấu trúc file](#3-pipeline--cấu-trúc-file)
5. [Bảng lệnh CLI](#4-bảng-lệnh-cli)
6. [Tính năng theo nhóm](#5-tính-năng-theo-nhóm-tóm-tắt)
7. [Cài đặt & yêu cầu](#6-cài-đặt--yêu-cầu)
8. [BASE path](#7-base-path-nơi-chứa-courses)
9. [Xử lý sự cố](#8-xử-lý-sự-cố-thường-gặp)

---

## 0. Mở app (1 click)

| Hệ điều hành | Cách mở |
|--------------|---------|
| **Windows** | Double-click **`SkoolDownloader.cmd`** · hoặc shortcut Desktop (`Nâng cao\Tao shortcut Desktop.cmd`) |
| **macOS** | Double-click **`SkoolDownloader.command`** · **Desktop → Skool Downloader** · **`~/Applications/Skool Downloader.app`** |
| **Linux** | `bash SkoolDownloader.command` |
| **Tạo shortcut** | macOS: **`Tao shortcut.command`** · Windows: **`Nâng cao\Tao shortcut Desktop.cmd`** |

```bash
# macOS / Linux
bash app/install_shortcut.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File app\install_shortcut.ps1
```

Lần đầu: tự tạo `app/venv` + cài thư viện (cần mạng).

---

## 1. Cách dùng nhanh (khuyến nghị)

### A. Một click từ URL (mới — 2.20)

```
1. Mở app → Dashboard
2. Chọn thư mục lưu (BASE)
3. Dán URL: https://www.skool.com/ten-khoa/classroom
4. (Tuỳ chọn) Bỏ tick Summary / Thumbnail / Resources / Transcript nếu muốn tắt
5. Chọn LLM: Chính DeepSeek · Fallback Gemini (có thể đổi) → Lưu LLM
6. ▶ Chạy
7. Nếu cần: đăng nhập Skool trong cửa sổ Chrome (giữ mở)
8. App tự: list chương → dump → tải video → transcript → summary.vi.md
```

### B. Quy trình thủ công (cũ)

```
1. ➕ Thêm khóa mới → dump browser
2. Màn tải: tick Transcript / Summary (mặc định BẬT)
3. ▶ Bắt đầu tải
```

### Chọn thư mục lưu

| Cách | Thao tác |
|------|----------|
| **GUI** | Dashboard → **📁 Thư mục lưu khóa** → **Chọn…** → **Lưu** |
| **Doctor** | Sidebar 🩺 → **Chọn…** / **Lưu** |
| **CLI** | `python app/doctor.py --set-base "D:/SkoolData"` |
| **Env** | `SKOOL_BASE=/path/to/folder` |

Khóa nằm tại: **`<BASE>/courses/<Tên khóa>/`**

---

## 2. Transcript & phụ đề

### Mặc định: **TỰ ĐỘNG BẬT**

Sau khi tải video, app chạy **faster-whisper**:

| Việc | Chi tiết |
|------|----------|
| **Ngôn ngữ** | **Auto-detect** theo từng video (`WHISPER_LANG=auto`) |
| **Giới thiệu bài** | Gộp nội dung **`description.md`** vào plain text |
| **Từng bài** | `video.txt` + `video.srt` (+ `video.lang`) **cùng folder** video |
| **Cả khóa** | **`all transcript.txt`** — gộp theo thứ tự bài, cách 3 dòng trống |

### Tắt / bật transcript

| Cách | Thao tác |
|------|----------|
| **GUI** | Màn tải khóa → **bỏ tick** *「Tự lấy transcript…」* (lưu vào settings) |
| **CLI tắt** | `python app/main.py --course "X" --no-transcribe` |
| **CLI ép bật** | `python app/main.py --course "X" --transcribe` |
| **Chỉ transcript** | `python app/main.py --course "X" --only transcribe` |
| **Config** | `app/config.py` → `AUTO_TRANSCRIBE = True/False` |
| **Settings** | `app/.settings.json` → `"auto_transcribe": true/false` |

### Ví dụ `video.txt`

```text
## Giới thiệu bài

Welcome to Day 1. In this lesson you will…

## Transcript (ngôn ngữ: en)

Hello everyone, today we will build…
```

### Ví dụ vị trí file

```text
courses/My Course/
  all transcript.txt
  01 - Intro/
    01 - Welcome/
      video.mp4
      video.txt          ← intro + transcript (auto lang)
      video.srt
      description.md
      resources/
```

### Model & cấu hình

```python
# app/config.py
AUTO_TRANSCRIBE = True
WHISPER_ENGINE = "faster-whisper"
WHISPER_MODEL = "distil-large-v3"   # hoặc "large-v3"
WHISPER_LANG = "auto"               # auto-detect; hoặc "en", "vi", …
TRANSCRIPT_INCLUDE_INTRO = True
ALL_TRANSCRIPT_NAME = "all transcript.txt"
```

---

## 2c. Nâng cấp khóa học (cập nhật đến hôm nay)

Sau khi đã tải xong khóa, có thể **làm mới curriculum** theo thị trường hiện tại:

| Bước | Việc |
|------|------|
| 0 | **Questionnaire** (mặc định **BẬT** — có thể tắt): trả lời mong muốn cập nhật |
| 1 | Phân tích khóa local (bài, tool được nhắc) |
| 2 | (Tuỳ chọn) Nghiên cứu web + LLM → **report DOCX** |
| 3 | Bạn có thể sửa thêm `_Upgrade_User_Notes.md` |
| 4 | LLM sinh **cấu trúc khóa mới** — loại bài cũ lỗi thời, thêm bài mới |
| 5 | (Tuỳ chọn) Sinh outline từng bài vào `_upgrade_v2/` |

- GUI: **Xuất & Báo cáo** → **🔬 Nâng cấp khóa (research)**  
- CLI:

```bash
python app/course_upgrade.py --course "TenKhoa" --research
# đọc report + sửa notes, rồi:
python app/course_upgrade.py --course "TenKhoa" --structure-only
# full (research + structure + viết bài):
python app/course_upgrade.py --course "TenKhoa" --full
```

Toggle: settings `course_upgrade_research` / `course_upgrade_web` (mặc định BẬT).  
LLM: cùng DeepSeek (chính) + Gemini (fallback) như summary.

### Course Studio (sau cấu trúc mới)

| Bước | Lệnh / GUI |
|------|------------|
| **1. Asset pack** | GUI **🎬 Asset pack** · `course_studio.py --assets --lang vi\|en` |
| | Mỗi bài: `talking_script.md` (cho AI video), workshop, use cases, resources, quiz… |
| **2. Master lang** | Chọn VI hoặc EN khi chạy assets (`course_master_lang`) |
| **3. Localize** | GUI **🌍 Localize hub** · `--localize --locales "zh-CN,ja,ko,es,pt-BR,id,hi,fr,de,ar"` |
| | Output: `_upgrade_v2/locales/<code>/…` · catalog ~40 ngôn ngữ: `--list-locales` |
| **4. Wizard FULL** | Sidebar **Course Studio** · `course_wizard.py --full` |
| **5. Video lab** | `course_video.py --prepare --run-queue` · ElevenLabs / HeyGen / Synthesia / local / **omnivoice** |
| | Voice map: `_brand_kit.json` · `--locale es` · GUI **🎥 Video lab** |
| **5b. OmniVoice TTS** | **Mặc định TẮT** · clone `~/Downloads/ref.wav` (conda `omnivoice`, MPS) |
| | GUI **🎙️ OmniVoice TTS** · `course_omnivoice.py --enable-all` rồi `--all --limit 3` |
| | Streamlit: `streamlit run ~/Downloads/omni_app.py` · http://localhost:8501 |
| **6. Publish** | `course_publish.py --all` → `_publish/` |
| **7. QA** | `course_qa.py --all` (diff + loc QA + eval + fact-check) |
| **8. Locale review** | `course_review.py --build` · approve/reject · GUI **👀 Locale review** |
| **9. Schedule** | `course_schedule.py --install --interval weekly` (launchd/cron) |
| **10. Curriculum board** | `course_board.py --show` / `--add-chapter` · GUI **📐 Board** |
| **11. Selective localize** | `--localize --only Intro --only MCP` |
| **12. Pipeline status** | `course_status.py --md` · GUI **📊 Pipeline status** |
| **13. Slides HTML** | `course_slides.py` → `_slides/` deck |
| **14. Ops / budget** | `course_ops.py --init --budget-cap 40 --glossary-add TERM` |
| **15. Review loop** | `--relocalize-rejected` · media keys GUI |
| **16. PPTX + thumbs** | `course_pptx.py` · `course_thumbs.py` |
| **17. Incremental upgrade** | `course_incremental.py --run` (schedule mặc định) |
| **18. Cost / golden eval** | `--cost-dashboard` · `--eval-golden` |
| **19. Skool clipboard + sales HTML** | `course_publish --clipboard --sales-html` |
| **20. Portfolio multi-course** | `course_portfolio.py --html` |
| **21. Board HTML + import JSON** | `course_board --html` · `--import-json` |
| **22. Student portal** | `course_portal.py --open` |
| **23. A/B titles · voice preview · approve→render** | `course_ab` · `--preview-voice` · `--render-approved` |
| **24. Board DnD** | `course_board --html` (kéo thả chapter/lesson) |
| **25. Competitor scan** | `course_competitor.py --llm` |
| **26. Notion + webhook** | `course_notion.py --export` · `COURSE_OS_WEBHOOK` |
| **27. FINISH ALL** | `course_finish.py --finish` · GUI **🚀 FINISH ALL** |
| **28. Feature registry** | `course_features.py` · `tests_course_os.py` |
| **29. OmniVoice TTS (opt-in)** | `course_omnivoice.py` · default **OFF** · board / playlist / portal audio |

### OmniVoice TTS (local Mac M5)

```bash
# UI Streamlit
conda activate omnivoice
export STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
streamlit run ~/Downloads/omni_app.py

# Course OS — mặc định TẮT; bật tường minh rồi render
python app/course_omnivoice.py --course "TenKhoa" --status
python app/course_omnivoice.py --course "TenKhoa" --enable-all   # hoặc --toggle-board
python app/course_omnivoice.py --course "TenKhoa" --all --limit 3
python app/course_omnivoice.py --course "TenKhoa" --disable-all
```

Cần: conda env `omnivoice`, `~/Downloads/ref.wav`. Output: `_upgrade_v2/.../tts_omnivoice.wav`.

---

## 2b. Summary từng bài (tiếng Việt) — tùy chọn

Sau khi có `description.md` / `video.txt`, có thể sinh **`summary.vi.md`** cho mỗi bài:

| Mục | Mô tả |
|-----|--------|
| **Purpose of the video** | Mục đích bài |
| **Summary** | Ngắn ~500 · TB ~700 · Dài ~1000 · Siêu dài ~1500 **từ** (theo độ dài nguồn) |
| **Key takeaways** | Ý then chốt |
| **Todo list** | Checklist chi tiết, step-by-step |
| **Quotes** | Trích dẫn |
| **Resources** | Tài nguyên / link |

- GUI: **Xuất & Báo cáo** → **📋 Summary từng bài (VI)**  
- CLI:

```bash
python app/lesson_summary.py --course "TenKhoa"           # chỉ bài chưa có
python app/lesson_summary.py --course "X" --force         # ghi đè
python app/lesson_summary.py --course "X" --lesson "01 - Chap/02 - Lesson"
```

- File gộp: `courses/<Khoa>/_All_Summaries.vi.md`  
- Cần **LLM API key** (cùng multi-provider như LLM Prompt).

---

## 3. Pipeline & cấu trúc file

| Bước | Module | Việc |
|------|--------|------|
| preflight | `preflight.py` | PASS/WARN/FAIL môi trường |
| folders | `folders.py` | Cây `NN - Tên` chương/bài |
| extras | `extras.py` | `description.md` + resources (link ~8h) |
| videos | `videos.py` | `video.<ext>` — native trước, rồi Loom/YT |
| **transcribe** | `transcribe.py` | **Mặc định BẬT** — Whisper auto-lang + all transcript.txt |
| audit | `audit.py` | `video_audit.txt` |

Resume an toàn: bài xong skip, mất mạng chờ, tải dở nối tiếp.

### Cấu trúc repo

```
Skool-Downloader/
├─ SkoolDownloader.cmd / .command   ← mở app
├─ Tao shortcut.command
├─ README.md
├─ docs/
│  ├─ FEATURES.md                   ← ⭐ danh sách tính năng đầy đủ
│  └─ HUONG_DAN_FEATURES_WORKFLOWS.md
├─ Nâng cao/                        ← shortcut CLI
├─ extractor.js
└─ app/                             ← mã nguồn
```

---

## 4. Bảng lệnh CLI

```bash
cd app   # hoặc dùng Nâng cao\Tai bang dong lenh.cmd

# Full pipeline (có auto transcript)
python main.py --course "TenKhoa"

# Tắt transcript lần này
python main.py --course "TenKhoa" --no-transcribe

# Chỉ video + (mặc định) transcript
python main.py --course "TenKhoa" --only videos

# Chỉ Whisper + all transcript.txt
python main.py --course "TenKhoa" --only transcribe --skip-preflight

# Tải đến khi đủ / native only / theo chương
python main.py --course "X" --until-clean
python main.py --course "X" --only videos --native-only
python main.py --course "X" --only videos --chapter "Ten chuong"
python main.py --course "X" --only videos --lesson "01 - A/02 - B"

# Queue nhiều khóa
python main.py --queue "Khoa A,Khoa B"
python main.py --queue-status

# Bảo trì
python doctor.py
python doctor.py --set-base "/path/to/data"
python selftest.py
python main.py --version
python cleanup.py --course "X" --apply
```

### LLM multi-provider (tóm tắt)

| Provider | Env key | Gợi ý model |
|----------|---------|-------------|
| **Grok (xAI)** | `XAI_API_KEY` | `grok-3`, `grok-3-mini` |
| Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` |
| OpenRouter | `OPENROUTER_API_KEY` | `x-ai/grok-3-mini`… |
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| Qwen / GLM / Kimi / DeepSeek | xem guide | catalog trong app |

GUI: **Xuất & Báo cáo** → chọn provider → dán key → **✨ LLM Prompt**.

---

## 5. Tính năng theo nhóm (tóm tắt)

Chi tiết từng mục: **[docs/FEATURES.md](docs/FEATURES.md)**.

| Nhóm | Nội dung chính |
|------|----------------|
| **Tải khóa** | Folders, extras, video multi-host, until-clean, chapter/lesson, fail retry, smart-update, workers |
| **Transcript** | Auto default, auto-detect lang, intro bài, all transcript.txt, tắt bằng GUI/CLI |
| **GUI** | Dashboard, manager, dump browser, queue, cloud, RAG chat, search, health, discovery |
| **AI / học** | Multi-LLM, dịch/tóm tắt, **summary từng bài (VI)**, Anki, quiz, study plan, vault |
| **Cloud** | R2, Google Drive, OneDrive, sync sau tải |
| **Catalog** | Discovery scrape communities → SQLite/CSV/Excel |
| **Ops** | Doctor, selftest, cleanup, disk report, launchers |

### Sidebar GUI

| Mục | Việc |
|-----|------|
| ⌂ Dashboard | BASE, KPI, card khóa, progress |
| ☰ Hàng đợi | Multi-course, workers 1–4 |
| 🔄 Cập nhật | Diff chương mới / thiếu / native expired |
| ☁ Cloud | R2 · Drive · OneDrive |
| 💬 Chat RAG | Hỏi nội dung đã tải |
| ✨ LLM Prompt | Dịch / cập nhật theo prompt |
| 🔍 Tìm kiếm | Transcript + mô tả + notes |
| 🌐 Web Viewer | Duyệt local |
| ❤ Health | Lịch quét kho |
| 🔎 Discovery | Catalog community Skool |
| 🩺 Doctor | Môi trường + BASE |

---

## 6. Cài đặt & yêu cầu

| Thành phần | Vì sao | Ghi chú |
|------------|--------|---------|
| **Python 3.9+** | App | 3.11+ khuyến nghị |
| **Node.js LTS** | yt-dlp vượt bot YouTube | nodejs.org |
| **ffmpeg** | Ghép/xử lý video | setup / ffdl |
| **faster-whisper** | Transcript | trong `requirements.txt` |
| **Playwright** | Dump browser / Discovery | `playwright install chromium` |

**Không cần cài tay** nếu dùng `SkoolDownloader.cmd` / `.command` (tự venv + pip).

> ⚠️ Thiếu **Node.js** là nguyên nhân #1 YouTube fail hàng loạt — `preflight` / Doctor sẽ cảnh báo.

---

## 7. BASE path (nơi chứa `courses/`)

Ưu tiên:

1. Biến môi trường `SKOOL_BASE`
2. `app/.settings.json` → `"skool_base"`
3. Tự nhận: có `courses/` cạnh hoặc trong repo
4. Mặc định: thư mục cha của repo

```bash
python app/doctor.py
python app/doctor.py --set-base "E:/SkoolData"
```

---

## 8. Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|------------|------------|
| YouTube fail hàng loạt | Cài Node.js LTS; `doctor` / preflight |
| Token native hết hạn | GUI **🔑 Cứu native** (re-dump trong ngày) |
| Resource 404 | Dump lại meta (link ~8h) |
| Transcript chậm / hết RAM | `WHISPER_MODEL` nhỏ hơn hoặc `WHISPER_COMPUTE=int8` |
| Không muốn Whisper | `--no-transcribe` hoặc bỏ tick GUI |
| Sai ngôn ngữ transcript | Để `auto` (mặc định) hoặc gán `WHISPER_LANG=vi` |
| GUI macOS treo | Dùng Homebrew Python (tránh Tk Xcode CLT) |
| Thiếu package | `python app/tools_fix.py --doctor-fix` |

---

## 9. Dump thủ công (tuỳ chọn, ngoài GUI)

1. Mở khóa Skool `/classroom`, F12 → Console.  
2. Dán [extractor.js](extractor.js).  
3. Từng chương: `skoolDumpChapter()`.  
4. Đặt JSON vào `<BASE>/courses/<Tên khóa>/`.  
5. `python app/main.py --course "<Tên khóa>"`.

Token native **~24h**, resource **~8h** → dump xong xử lý trong ngày.

---

## Tài liệu liên quan

| File | Nội dung |
|------|----------|
| **[docs/FEATURES.md](docs/FEATURES.md)** | Checklist / inventory mọi tính năng |
| **[docs/HUONG_DAN_FEATURES_WORKFLOWS.md](docs/HUONG_DAN_FEATURES_WORKFLOWS.md)** | Workflow A–G, LLM, phím tắt |
| `docs/SkoolArchiver_Huong_Dan_Su_Dung.docx` | SOP vận hành (Word) |

---

*Skool Downloader — lưu khóa Skool offline, học lại bất cứ lúc nào.*
