# Skool Downloader — Hướng dẫn Features & Workflows

> Phiên bản app: **2.15.1+** · Cập nhật: 2026-07  
> Launcher: `SkoolDownloader.cmd` (Win) · `SkoolDownloader.command` (macOS) · CLI: `app/main.py` · LLM: `app/llm_prompt.py`

Tài liệu này mô tả **tính năng**, **luồng làm việc**, **giao diện video/progress**, và **cấu hình LLM** (Claude, OpenAI, **Grok**, Gemini, OpenRouter, Qwen, GLM, Kimi, …).

---

## 1. Cài đặt & khởi động (dễ nhất)

### 1.1 Mở app bằng 1 click

| OS | Bước |
|----|------|
| **Windows** | Double-click **`SkoolDownloader.cmd`**. Tạo icon Desktop: chạy **`Nâng cao\Tao shortcut Desktop.cmd`** một lần. |
| **macOS** | Double-click **`SkoolDownloader.command`**. Tạo icon Desktop + App: double-click **`Tao shortcut.command`** (hoặc `bash app/install_shortcut.sh`). Sau đó mở từ **Desktop → Skool Downloader** hoặc **`~/Applications/Skool Downloader.app`**. |
| **Linux** | `bash SkoolDownloader.command` hoặc sau `install_shortcut.sh` dùng menu ứng dụng. |

Lần đầu: tự tạo `app/venv` + `pip install -r requirements.txt` (cần mạng).  
macOS nếu báo “không mở được”: **chuột phải → Open** (lần đầu).  
macOS nếu GUI không hiện: dùng **Homebrew Python** (app tự ưu tiên; tránh Python Xcode CLT — Tk bị treo).

### 1.2 CLI (Windows / macOS / Linux)

```bash
cd app
python3 main.py --version
python3 doctor.py
python3 selftest.py --quick
# hoac mo GUI truc tiep (khi da co venv):
bash start.sh
# neu thieu Chromium (dump browser):
./venv/bin/python -m playwright install chromium
```

### 1.3 Chọn thư mục lưu khóa (BASE / output)

**Trong app (khuyến nghị):**

1. Mở **Dashboard**
2. Ô **📁 Thư mục lưu khóa (output)** → **Chọn…** → chọn folder
3. **Lưu** — app ghi `app/.settings.json` (`skool_base`) và tạo `courses/` nếu chưa có

Cũng có cùng điều khiển ở **🩺 Doctor**.

**CLI / env (tùy chọn):**

```bash
python doctor.py --set-base "E:/SkoolData"
# hoặc
export SKOOL_BASE="/Users/you/SkoolData"
```

Ưu tiên: `SKOOL_BASE` env → `settings.json` → auto-detect.

Cấu trúc sau khi lưu:

```
BASE/                          ← folder bạn chọn
├─ courses/
│  ├─ TenKhoa/
│  │  ├─ 01 - Chuong/
│  │  │  └─ 01 - Bai/
│  │  │       description.md · video.mp4 · video.txt · video.srt · notes.md
│  │  ├─ _download_progress.json   ← progress live khi đang tải
│  │  ├─ _TongHop.md · video_fails.json
│  │  └─ .rag/
│  ├─ _backups/
│  └─ _health.json
└─ SkoolCourse/                # layout cũ (legacy)
```

### 1.4 Giao diện — thông tin video & progress live

| Vùng UI | Nội dung hiển thị |
|---------|-------------------|
| **KPI Dashboard** | Số khóa · **Video đã tải x/y** · **Dung lượng video** · Cảnh báo (token / fail) |
| **Card khóa** | `Video x/y · N chương · dung lượng · còn Z` · progress bar · badge (✓ đủ / ⏳ còn / 🔑 hết hạn) |
| **Trình tải** | Header: `Video done/total · chương · size · nguồn (youtube/loom/native)` |
| **Dòng chương** | `▶ done/total` + dung lượng chương · nút ⬇ Chương |
| **Dòng bài** | Trạng thái ✓ xong / ⏳ đang / • chờ · **size video** · host · ⬇ / ★ / ✎ |
| **Panel live (khi tải)** | **Khóa · Folder · Video x/y · Bài hiện tại · progress % · ETA** + 3 cột: Đã xong / Đang·lỗi / Chuẩn bị |

File progress: `courses/<TenKhoa>/_download_progress.json` (app đọc ~1s/lần khi đang tải).

---

## 2. Workflows chính

### Workflow A — Lưu trữ khóa mới (end-to-end)

```
Dashboard → Chọn… folder lưu → Lưu
  → ➕ Thêm khóa mới
  → 1. Mở Skool & đăng nhập (trình duyệt app / Playwright Chromium)
  → 2. Lấy danh sách chương
  → 3. Tick chương → Dump JSON
  → Trình tải: xem Video x/y · ⬇ Tải toàn bộ (hoặc theo chương/bài)
  → Theo dõi panel live (khóa / folder / video / bài)
  → (tuỳ chọn) Phụ đề Whisper
  → Xuất & Báo cáo / Chat RAG / Cloud
```

**CLI tương đương:**

```bash
# Sau khi dump JSON vào courses/TenKhoa/
python main.py --course "TenKhoa" --until-clean
python main.py --course "TenKhoa" --transcribe
python main.py --course "TenKhoa" --index
```

### Workflow B — Cập nhật khóa (bài mới / token hết hạn)

```
Dashboard → Cập nhật (trên card khóa)
  → Diff: chương mới · bài thiếu · native hết hạn
  → Dump lại chương cần thiết
  → ⚡ Thiếu (smart-update) hoặc ↻ Fail
```

```bash
python updates.py --course "X" --smart-plan
python main.py --course "X" --only videos --smart-update --until-clean
python main.py --course "X" --only videos --retry-failed --until-clean
```

### Workflow C — Multi-course hàng đợi

```
Dashboard → tick nhiều khóa → + Hàng đợi
  → Sidebar ☰ Hàng đợi → workers 1–4 → Chạy
```

```bash
python main.py --queue "KhoaA,KhoaB" --until-clean
python main.py --smart-batch --smart-batch-run
```

### Workflow D — Học offline (notes → quiz → playlist → lịch)

```
Trình tải → ★ bookmark · ✎ notes
  → Xuất & Báo cáo → Offline quiz
  → Dashboard → ▶ Học · 📅 Plan (ICS)
```

```bash
python notes.py --course "X" --list
python quiz.py --course "X" --build
python quiz.py --course "X" --play
python learn_playlist.py --all --write
python study_plan.py --all --days 14
```

### Workflow E — Dịch / cập nhật nội dung bằng LLM (prompt tùy chọn)

```
Xuất & Báo cáo
  → Cấu hình API (Claude / Grok / Gemini / Qwen / …)
  → Đặt Fallback chain
  → ✨ LLM Prompt
       · Chọn khóa + nguồn (tonghop / lesson / notes)
       · Preset hoặc tự nhập prompt
       · Provider + model + fallback
       · ▶ Chạy → file .md trong thư mục khóa
```

Chi tiết mục **§4**.

### Workflow F — Backup knowledge & cloud

```
☁ Cloud → Backup local / Backup+upload / Restore
Dashboard card → Sync · Pack
```

```bash
python knowledge_pack.py --course "X"
python -m cloud.pack_backup --course "X" --backup --upload
python -m cloud.sync --course "X" --mode knowledge
```

### Workflow G — Health & vận hành

```
🌐 Web tools → Health / Digest / Site tĩnh
🩺 Doctor → Fix 1-click · ↑ yt-dlp
```

```bash
python health_check.py --write --digest --notify
python doctor.py --fix
python export_site.py --open
```

---

## 3. Bản đồ tính năng (tóm tắt)

| Nhóm | Tính năng |
|------|-----------|
| **Core** | Pipeline folders→extras→videos→transcribe→audit · preflight · resume · until-clean |
| **GUI v2** | Sidebar · dark/light · density · dashboard KPI · wizard dump · manager chương/bài |
| **Output** | Chọn folder lưu (BASE) trên Dashboard/Doctor · persist `skool_base` |
| **Video UI** | Card khóa Video x/y · size · host · trạng thái bài · panel live 3 cột |
| **Tải thông minh** | Fail-driven retry · smart-update · parallel workers · adaptive 429 · ETA live |
| **Queue** | Multi-course · workers 1–4 · requeue failed · smart-batch |
| **Knowledge** | Pack zip · backup/restore · notes · content-diff · Anki · quiz · playlist · ICS |
| **RAG** | Catalog + TF-IDF · dense embed (tuỳ chọn) · chat multi-course · search + notes |
| **Cloud** | R2 · Google Drive · OneDrive · sync badge · after-download |
| **Web** | Local viewer · static site · health schedule · tray |
| **LLM** | Prompt tùy chỉnh · multi-provider (Grok/Claude/Gemini/…) · fallback · presets |
| **UX** | Favorites · alias · shortcuts · last-course · bookmarks · disk report |

---

## 4. LLM — cấu hình & sử dụng

### 4.1 Providers hỗ trợ

| ID | Tên | Base URL / API | Env key |
|----|-----|----------------|---------|
| `anthropic` | Claude | Anthropic Messages | `ANTHROPIC_API_KEY` |
| `openai` | OpenAI | `api.openai.com/v1` | `OPENAI_API_KEY` |
| **`grok`** | **Grok (xAI)** | **`https://api.x.ai/v1`** | **`XAI_API_KEY`** (hoặc `GROK_API_KEY`) |
| `openrouter` | OpenRouter | `openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| `gemini` | Google Gemini | Generative Language API | `GEMINI_API_KEY` |
| `glm` | 智谱 GLM | open.bigmodel.cn | `ZHIPU_API_KEY` |
| `qwen` | 通义 Qwen | DashScope compatible | `DASHSCOPE_API_KEY` |
| `deepseek` | DeepSeek | api.deepseek.com | `DEEPSEEK_API_KEY` |
| `kimi` | Kimi/Moonshot (alias `kiwi`) | api.moonshot.cn | `MOONSHOT_API_KEY` |
| `siliconflow` | 硅基流动 | api.siliconflow.cn | `SILICONFLOW_API_KEY` |
| `doubao` | 豆包 | Volcengine ARK | `ARK_API_KEY` |
| `stepfun` | 阶跃星辰 | api.stepfun.com | `STEPFUN_API_KEY` |
| `yi` | 零一万物 | api.lingyiwanwu.com | `YI_API_KEY` |
| `baichuan` | 百川 | api.baichuan-ai.com | `BAICHUAN_API_KEY` |
| `minimax` | MiniMax | api.minimax.chat | `MINIMAX_API_KEY` |
| `groq` | Groq | api.groq.com/openai/v1 | `GROQ_API_KEY` |
| `custom` | Ollama/vLLM/… | URL tùy chỉnh | `CUSTOM_LLM_API_KEY` |

**Grok models gợi ý:** `grok-3` · `grok-3-mini` · `grok-3-fast` · `grok-2-1212`  
Qua OpenRouter: `x-ai/grok-3-mini` · `x-ai/grok-3`

### 4.2 Cấu hình Grok (xAI) — GUI

1. Mở **Xuất & Báo cáo**
2. **Provider** → chọn `grok`
3. **Model** → ví dụ `grok-3-mini`
4. **API Key** → dán key từ [console.x.ai](https://console.x.ai)
5. **💾 Lưu** · **Đặt mặc định** (nếu muốn Grok là primary)
6. (Tuỳ chọn) **Fallback**: `grok,openrouter,gemini,qwen,openai,anthropic`

### 4.3 Cấu hình Grok — CLI

```bash
# Lưu key + model + đặt mặc định
python app/llm_prompt.py --set-key grok "xai-..."
python app/llm_prompt.py --set-model grok grok-3-mini
python app/llm_prompt.py --set-provider grok

# Fallback có Grok
python app/llm_prompt.py --set-fallback "grok,openrouter,gemini,qwen,glm,kimi,openai,anthropic"

# Kiểm tra
python app/llm_prompt.py --list-providers
python app/llm_prompt.py --check

# Chạy dịch bằng Grok
python app/llm_prompt.py --course "TenKhoa" --source tonghop --preset translate_vi --provider grok

# Prompt tự do
python app/llm_prompt.py --course "TenKhoa" --source tonghop \
  --user-prompt "Dịch sang tiếng Việt, giữ thuật ngữ tiếng Anh" \
  --provider grok --model grok-3
```

Env:

```bash
export XAI_API_KEY="xai-..."
export LLM_PROVIDER=grok
```

### 4.4 Preset LLM (prompt có sẵn)

| Preset | Việc | Output gợi ý |
|--------|------|----------------|
| `translate_vi` | Dịch → tiếng Việt | `*.vi.md` |
| `translate_en` | Dịch → English | `*.en.md` |
| `update_style` | Viết lại gọn, rõ | `*.updated.md` |
| `summary_todo` | Tóm tắt + to-do | `*.summary.md` |
| `extract_terms` | Glossary | `*.glossary.md` |
| `custom` | **Tự nhập 100%** | `*.llm.md` |

**Placeholder:** `{{content}}` · `{{user_prompt}}` · `{{course}}`

### 4.5 Nguồn nội dung (`--source`)

| Source | Ý nghĩa |
|--------|---------|
| `tonghop` | `_TongHop.md` (tự gộp nếu thiếu) |
| `tonghop_vi` | `_TongHop.vi.md` |
| `tomtat` | `_TomTat.md` |
| `notes` | `_Notes_All.md` |
| `lesson` | 1 bài (`--lesson "01 - C/01 - L"`) |
| `file` | File bất kỳ (`--file path`) |

### 4.6 Fallback hoạt động thế nào?

1. Thử **provider đang chọn** + model  
2. Nếu lỗi (key, 429, 5xx, network) → thử provider **tiếp theo trong chain** (chỉ những provider **đã có key**)  
3. Log: `LLM try [qwen]…` · `✗ …` · `✓ fallback OK via gemini`

Tắt fallback: GUI bỏ tick · CLI `--no-fallback`.

### 4.7 Ví dụ prompt người dùng

- `Dịch sang tiếng Việt, giọng trang trọng, giữ thuật ngữ EN trong ngoặc`
- `Viết lại ngắn 50%, bullet points, thêm To-do cho giáo viên THPT`
- `Chỉ tóm tắt transcript, bỏ phần chào hỏi`
- `Trích 20 thuật ngữ automation quan nhất + giải thích 1 câu`

Lưu preset:

```bash
python app/llm_prompt.py --save-preset my_vi_edu --title "Dich VI giao duc" \
  --system "Ban la bien dich vien giao duc VN." \
  --prompt "{{user_prompt}}\n\n{{content}}"
```

---

## 5. Phím tắt GUI

| Phím | Việc |
|------|------|
| ⌘/Ctrl+K hoặc / | Focus tìm kiếm |
| ⌘/Ctrl+1…4 | Dashboard / Queue / Chat / Cloud |
| ⌘/Ctrl+R · F5 | Làm mới Dashboard |
| ⌘/Ctrl+, | Doctor |
| F1 | Trợ giúp phím tắt |
| ★ trên card | Ghim khóa |
| Aa | Alias tên hiển thị |
| ✎ trên bài | Ghi chú notes.md |

---

## 6. CLI tham chiếu nhanh

```bash
# Pipeline
python app/main.py --course "X" --until-clean --workers 2
python app/main.py --course "X" --only videos --smart-update
python app/main.py --course "X" --only videos --retry-failed

# Knowledge
python app/knowledge_pack.py --course "X"
python app/anki_export.py --course "X"
python app/quiz.py --course "X" --play
python app/vault_export.py --course "X"
python app/vault_export.py --course "X" --format notion

# Search / health
python app/search_lib.py "webhook" --snippet
python app/health_check.py --digest --write
python app/disk_report.py --write

# LLM
python app/llm_prompt.py --list-providers
python app/llm_prompt.py --list-presets
python app/llm_prompt.py --course "X" --preset translate_vi --provider grok
```

Helpers Windows: folder **`Nâng cao/`** (`LLM Prompt.cmd`, `Doctor.cmd`, …).

---

## 7. Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|------------|------------|
| YouTube bot / 429 | Cài Node.js · cookies · `--until-clean` · hạ workers · adaptive |
| Native 403 token | Dump lại chương · Cứu native |
| Không thấy khóa | Dashboard → **Chọn…** BASE đúng folder · Doctor → Lưu BASE · `courses/` |
| GUI macOS không hiện | Homebrew Python · xóa `app/venv` · mở lại `SkoolDownloader.command` |
| Playwright thiếu Chromium | `app/venv/bin/python -m playwright install chromium` |
| Không thấy progress video | Đang tải? Xem panel Dashboard/manager · file `_download_progress.json` |
| LLM “Chưa có API key” | Xuất & Báo cáo → dán key provider · `--check` |
| Grok 401 | Kiểm tra `XAI_API_KEY` · model id đúng (`grok-3-mini`) |
| Grok/network CN | Dùng OpenRouter `x-ai/grok-3-mini` hoặc fallback `qwen`/`glm` |
| Fallback không chạy | Chỉ thử provider **đã lưu key** · xem log `LLM try […]` |
| Không thấy khóa | Doctor → BASE path · `courses/` |

---

## 8. Bảo mật

- API keys lưu **local** trong `app/.settings.json` (không commit)
- Ưu tiên env: `XAI_API_KEY`, `ANTHROPIC_API_KEY`, …
- Không gửi video lên cloud mặc định (mode **knowledge**)
- LLM chỉ nhận text bạn chọn (tonghop / lesson / notes)

---

## 9. Tài liệu liên quan

| File | Nội dung |
|------|----------|
| [README.md](../README.md) | Tổng quan + lệnh CLI |
| `docs/SkoolArchiver_Huong_Dan_Su_Dung.docx` | Hướng dẫn sử dụng (Word) |
| `docs/SkoolArchiver_SOP_Van_Hanh.docx` | SOP vận hành |
| `docs/SkoolArchiver_Tai_Lieu_Dev_SOP.docx` | Dev SOP |
| `app/llm_providers.py` | Catalog provider + model |
| `app/llm_prompt.py` | CLI/API chạy prompt |

---

*Skool Downloader — local-first archive + knowledge + multi-LLM prompts.*
