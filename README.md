# Skool Archiver

Công cụ lưu trữ **toàn bộ một khóa học Skool** về máy: cây thư mục theo chương/bài, video (native Skool + Loom + YouTube), mô tả bài, tài liệu (resources) và **phụ đề tiếng Anh (Whisper)** — chạy bằng **một lệnh**, có **kiểm tra môi trường trước khi chạy** và **báo lỗi kèm cách xử lý**.

> Phiên bản hiện tại: **2.13.0** — multi-LLM + **Grok (xAI)** · Gemini · OpenRouter · Qwen · GLM · Kimi · … + fallback.  
> Hướng dẫn features/workflows: **[docs/HUONG_DAN_FEATURES_WORKFLOWS.md](docs/HUONG_DAN_FEATURES_WORKFLOWS.md)** · `python app/main.py --version`  
> Đã kiểm chứng trên khóa *AI Automations by Jack* (584 bài, ~170 GB).

---

## 0. Cấu trúc thư mục

Chỉ những thứ bạn cần dùng nằm ở ngoài; toàn bộ mã nguồn kỹ thuật gom trong `app/`.

```
Archiver/
├─ SkoolArchiver.cmd             ← ⭐ BẤM PHÁT LÀ CHẠY (lần đầu tự cài → mở giao diện)
├─ Nâng cao/                     ← công cụ dòng lệnh (KHÔNG bắt buộc)
│  ├─ Tai bang dong lenh.cmd     ← chạy pipeline bằng dòng lệnh
│  ├─ Doctor.cmd / Doctor fix.cmd
│  ├─ LLM Prompt.cmd             ← dịch/cập nhật theo prompt (multi-LLM)
│  ├─ Web Viewer.cmd · Health check.cmd
│  ├─ Knowledge pack · Pack backup · Smart update/batch
│  ├─ Anki · Quiz · Vault · Study plan · Disk report
│  └─ …
├─ extractor.js                  ← dán vào Console trình duyệt để dump
├─ README.md
├─ docs/
│  ├─ HUONG_DAN_FEATURES_WORKFLOWS.md  ← ⭐ features + workflows + LLM
│  └─ *.docx                     ← SOP / hướng dẫn Word
├─ logs/
└─ app/                          ← mã nguồn (Python + PowerShell)
```

→ **Bình thường chỉ cần duy nhất `SkoolArchiver.cmd`.** Lần đầu trên máy mới nó **tự cài** (tạo venv + thư viện + ffmpeg), các lần sau **mở giao diện ngay** — không cần chạy setup hay run gì cả. Folder `Nâng cao/` chỉ dùng khi muốn thao tác bằng dòng lệnh.

**Đọc trước khi dùng nâng cao:** [docs/HUONG_DAN_FEATURES_WORKFLOWS.md](docs/HUONG_DAN_FEATURES_WORKFLOWS.md) — workflows A–G, LLM multi-provider (Grok/Claude/Gemini/Qwen…), phím tắt, xử lý sự cố.

---

### LLM multi-provider (tóm tắt)

| Provider | ID CLI | Key env | Models gợi ý |
|----------|--------|---------|----------------|
| **Grok (xAI)** | `grok` | `XAI_API_KEY` | `grok-3`, `grok-3-mini` |
| Claude | `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `x-ai/grok-3-mini`, … |
| Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| Qwen / GLM / Kimi / DeepSeek | `qwen` `glm` `kimi` `deepseek` | xem guide | catalog trong app |

GUI: **Xuất & Báo cáo** → chọn provider → dán key → **✨ LLM Prompt**. Fallback tự thử provider khác khi lỗi.

---

## 1. Pipeline làm gì

Giao diện gọi pipeline này; muốn chạy tay thì dùng `Nâng cao\Tai bang dong lenh.cmd` → `app/run.ps1` → `app/main.py`, chạy lần lượt (có **preflight** kiểm tra môi trường ở đầu):

| Bước | Module | Việc |
|------|--------|------|
| *preflight* | [preflight.py](app/preflight.py) | Kiểm tra Python/Node/ffmpeg/yt-dlp/đĩa/JSON → PASS/WARN/FAIL. FAIL thì dừng |
| `folders`    | [folders.py](app/folders.py)    | Dựng cây `NN - Tên` cho từng chương/bài (tự tạo cả folder **chương** cho khóa mới) |
| `extras`     | [extras.py](app/extras.py)      | Ghi `description.md` + tải `resources/` *(link resource hết hạn sau **8h**)* |
| `videos`     | [videos.py](app/videos.py)      | Tải video → `video.<ext>` (yt-dlp). 2 lượt: **native trước** *(token **24h**)*, rồi Loom/YouTube. **Phân loại lỗi tự động** |
| `transcribe` | [transcribe.py](app/transcribe.py) | *(tùy chọn `--transcribe`)* faster-whisper → `video.txt` + `video.srt` |
| `audit`      | [audit.py](app/audit.py)        | Đối chiếu JSON ↔ file thực, xuất `video_audit.txt` |

Toàn bộ **resume an toàn**: bài xong tự skip, mất mạng tự chờ, tải dở tự nối tiếp, chạy lại bao nhiêu lần cũng được.

---

## 1b. Giao diện (SkoolArchiver.cmd) — cách dùng chính

Double-click **`SkoolArchiver.cmd`** → mở app cửa sổ. Lần đầu trên máy mới nó tự cài môi trường rồi mới mở. Màn hình chính là **Dashboard** (toàn kho khóa); wizard tải / trình quản lý chương-bài vẫn dùng như trước.

**Trình tải theo chương/bài:** Sau khi mở một khóa, app liệt kê tất cả chương, bấm **▸** để mở các bài. Có thể **⬇ Tải cả chương**, **⬇ từng bài**, hoặc **⬇ Tải toàn bộ**; **■ Dừng** bất cứ lúc nào. CLI: `--chapter`, `--lesson`.

**Phase 1 — nâng cao (sidebar):**

| Tính năng | Mô tả | CLI / ghi chú |
|-----------|-------|----------------|
| **⌂ Dashboard** | Card mỗi khóa: % / dung lượng / badge (đủ · còn N · hết hạn token) · quick actions | `progress.scan_all` |
| **☰ Hàng đợi** | Multi-course queue, **song song 1–4 workers**, pause/resume, `queue_state.json` | `--queue "A,B"` · `queue_engine --workers 2 --run` |
| **🔄 Cập nhật v2** | Diff chương mới + bài thiếu local + native hết hạn; quét local toàn kho | `updates.py` · `_update_diff.json` |
| **☁ Cloud** | **R2** · **Google Drive** · **OneDrive**; knowledge mode; sync 1 khóa / tất cả | `python -m cloud.sync --course X` · `--all` · `--test` |
| **💬 Chat RAG** | TF-IDF vector + keyword; **multi-course**; Claude trả lời kèm nguồn | `python -m rag.chat --course X --ask "..."` · `--multi "A,B"` |
| **✨ LLM Prompt** | Dịch / cập nhật theo **prompt bạn chọn**; multi-provider + fallback | `llm_prompt.py` · GUI Xuất & Báo cáo |
| **🔍 Tìm kiếm** | Tìm transcript/mô tả/**notes** toàn kho; báo cáo tiến độ MD | `python search_lib.py "webhook"` · `--report` |
| **🌐 Web Viewer** | Duyệt knowledge local (mobile-friendly + PWA manifest) | `python web_viewer.py` |
| **❤ Health schedule** | Quét kho hàng ngày → `_health.json`; Task / launchd | `python health_check.py --write --notify` |
| **📄 Site tĩnh** | Export HTML offline (`courses/_site`) + tìm client-side | `python export_site.py --open` |
| **🧠 Dense embed** | (Tuỳ chọn) sentence-transformers; auto fallback TF-IDF | `pip install sentence-transformers` rồi Index lại |
| **🖥 Tray** | (Tuỳ chọn) icon khay: Web / Health / GUI | `pip install pystray pillow` · `python tray_app.py` |

**Hoàn thiện việc tải (Nhóm B):**

| Tính năng | Mô tả |
|-----------|-------|
| **Tải tiếp khóa dở** | Dashboard / manager hiện `đã tải / tổng · dung lượng · còn N bài`; chỉ tải phần thiếu |
| **Tự thử lại đến khi tải đủ** | Tick ô tùy chọn → lặp `tải → kiểm tra` khi bị giới hạn (CLI: `--until-clean`) |
| **Kiểm tra cập nhật khóa** | So danh sách chương trên Skool với bản đã lưu, **chương MỚI tick sẵn** + tóm tắt diff |
| **Cứu bài native hết hạn** | Đọc JWT `exp` → nút **🔑 Cứu bài native** lấy token mới rồi tải lại |
| **Xóa khóa** | Xóa khóa đã chọn (Thùng rác nếu có `send2trash`) |

**Xuất & Báo cáo (Nhóm A)** — nút **📄 Xuất & Báo cáo** ở thanh bên:

| Tính năng | Mô tả | Yêu cầu |
|-----------|-------|---------|
| **Gộp & xuất Word** | Gộp `description.md` + lời giảng (`video.txt`) toàn khóa → `_TongHop.md` **và** `_TongHop.docx` | `python-docx` cho bản `.docx` (thiếu vẫn có `.md`) |
| **Dịch tiếng Việt** | Dịch file tổng hợp sang tiếng Việt → `_TongHop.vi.md` | **API key Claude** (dán ngay trong app) **hoặc** `deep-translator` (Google, miễn phí) |
| **Tóm tắt + To-do (AI)** | Tóm tắt từng chương + **việc áp dụng cho Trường Việt Anh** → `_TomTat.md` | **API key Claude** |

> **API key Claude điền sống trong app:** ở màn “📄 Xuất & Báo cáo” có ô dán API key (lấy ở console.anthropic.com → API Keys). Key lưu tại `app\.settings.json` **trên máy này** (đã `.gitignore`), chỉ gửi tới API Claude. Vẫn dùng được biến môi trường `ANTHROPIC_API_KEY` nếu thích (biến môi trường được ưu tiên).

→ Chuỗi trọn vẹn: **tải → bóc lời giảng → dịch → tóm tắt/to-do → xuất file gửi sếp.**

---

## 1c. BASE path (nơi chứa `courses/`)

App tìm thư mục gốc dữ liệu theo thứ tự:

1. Biến môi trường `SKOOL_BASE`
2. `app/.settings.json` → `"skool_base"`
3. Tự nhận: có `courses/` cạnh repo (layout `SkoolProject/Archiver`) **hoặc** `courses/` trong repo
4. Mặc định: thư mục cha của repo

Kiểm tra / sửa:

```powershell
python app\doctor.py
python app\doctor.py --set-base "E:\SkoolProject"
```

Hoặc sidebar **🩺 Doctor** trong GUI.

---

## 2. Yêu cầu

| Thành phần | Vì sao | Cài |
|------------|--------|-----|
| **Python 3.9+** | chạy pipeline | python.org |
| **Node.js (LTS)** | yt-dlp cần JS runtime để **vượt chặn bot YouTube** | https://nodejs.org *(setup tự thử cài qua winget)* |
| **ffmpeg** | ghép video | tự cài qua `setup.ps1` |
| yt-dlp, faster-whisper | tải + phụ đề | qua `setup.ps1` |

> ⚠️ **Thiếu Node.js là nguyên nhân #1 khiến YouTube fail hàng loạt.** `preflight` sẽ cảnh báo nếu thiếu.

---

## 3. Cài đặt (máy mới)

**Không cần làm gì riêng** — cứ double-click **`SkoolArchiver.cmd`**, lần đầu nó tự tạo venv + cài thư viện + ffmpeg rồi mở giao diện. (Nếu máy chưa có Python, nó hiện thông báo bảo tải Python 3.11+ ở python.org, nhớ tick *Add to PATH*.)

> 💡 Máy hiện tại **đã có sẵn** `..\whisper\venv` đầy đủ (yt-dlp + faster-whisper + model) → `SkoolArchiver.cmd` tự dùng venv đó, mở giao diện tức thì.
>
> 🔒 Nếu Windows chặn chạy `.ps1` (ExecutionPolicy): cứ dùng file **`.cmd`** (đã tự bypass), khỏi chỉnh gì.

---

## 4. Quy trình lưu trữ một khóa mới

### Bước A — Dump dữ liệu khóa (trình duyệt, ĐÃ đăng nhập Skool)

> ❗ Thủ công vì cần phiên đăng nhập. Token native **24h**, link file **8h** → **dump xong xử lý ngay trong ngày**.

1. Mở khóa ở trang `…/classroom`, bật **F12 → Console**.
2. Dán toàn bộ [extractor.js](extractor.js) → Enter.
   - Ở **/classroom**: in danh sách chương + tự tải **`_chapters.json`** (thứ tự chương).
   - Ở một **trang chương**: tự dump `vid__<Chương>.json` + `meta__<Chương>.json`.
3. Lần lượt mở từng chương ở sidebar, gõ `skoolDumpChapter()`.
4. Gom mọi file vừa tải vào: `E:\SkoolProject\courses\<Tên khóa>\`

### Bước B — Một lệnh

> Cách nhanh nhất là dùng giao diện (`SkoolArchiver.cmd`). Các ví dụ `run.cmd` dưới đây nay nằm ở **`Nâng cao\Tai bang dong lenh.cmd`** (cùng tham số):

```powershell
.\run.cmd --course "<Tên khóa>"
.\run.cmd --course "<Tên khóa>" --transcribe  # kèm phụ đề luôn
```

Xong. Video + tài liệu + mô tả nằm trong `courses\<Tên khóa>\`, báo cáo ở `video_audit.txt`.

---

## 5. Bảng lệnh

```powershell
.\run.cmd --list-courses                       # liệt kê các khóa
.\run.cmd --course "X"                          # full pipeline (có preflight)
.\run.cmd --course "X" --transcribe             # + phụ đề
.\run.cmd --course "X" --until-clean            # tự thử lại đến khi tải đủ (chờ nếu bị giới hạn)
.\run.cmd --course "X" --only videos            # 1 bước: folders|extras|videos|transcribe|audit
.\run.cmd --course "X" --only videos --native-only  # chỉ tải native (cứu bài hết token)
.\run.cmd --course "X" --only videos --dry-run  # liệt kê, không tải
.\run.cmd --course "X" --cookies-file cookies.txt   # nếu video cần đăng nhập
.\run.cmd --queue "Khoa A,Khoa B"               # multi-course queue (thêm + chạy)
.\run.cmd --queue-add "Khoa A,Khoa B"          # chỉ thêm vào hàng đợi
.\run.cmd --queue-run                           # chạy hết job queued
.\run.cmd --queue-status                        # xem hàng đợi
python app\preflight.py --course "X"           # chỉ kiểm tra môi trường
python app\doctor.py                           # doctor full (core + BASE + phase modules)
python app\doctor.py --set-base "E:\SkoolProject"
python app\selftest.py                         # doctor + unit smoke
python app\main.py --version
python app\queue_engine.py --requeue-failed    # thu lai job failed/stopped
python app\cleanup.py --course "X" --fails     # xem video_fails.json
python app\cleanup.py --course "X" --apply     # xoa file .part/.ytdl thua
python app\main.py --course "X" --only videos --retry-failed --until-clean
python app\main.py --course "X" --retry-failed --fail-codes rate,network
python app\main.py --course "X" --only videos --missing-only --until-clean
python app\main.py --course "X" --only videos --smart-update --until-clean
python app\main.py --course "X" --only videos --chapters "Chap A||Chap B"
python app\updates.py --course "X" --smart-plan
python app\knowledge_pack.py --course "X"      # zip text/resources (khong video)
python -m cloud.pack_backup --course "X" --backup
python -m cloud.pack_backup --course "X" --backup --upload
python -m cloud.pack_backup --list
python -m cloud.pack_backup --restore path\to\pack.zip --course "X"
python app\search_lib.py "webhook" --snippet   # highlight + folder bai
python app\main.py --course "X" --only videos --workers 3   # parallel bai (1-4)
python app\main.py --course "X" --only videos --workers 3   # adaptive ha workers khi 429
python app\main.py --resume --only videos --missing-only    # mo last_course
python app\main.py --course "X" --notify                    # toast khi xong
python app\main.py --smart-batch                            # queue smart-update moi khoa thieu
python app\main.py --smart-batch --smart-batch-run
python app\updates.py --smart-batch
python app\session_state.py --last
python app\session_state.py --list-bm
python app\health_check.py --digest --write --notify        # digest + delta
python app\anki_export.py --course "X"                      # Anki TSV
python app\anki_export.py --course "X" --cloze
python app\quiz.py --course "X" --build
python app\quiz.py --course "X" --play
python app\learn_playlist.py --all --write                  # playlist Hoc tiep
python app\content_diff.py --course "X" --snapshot
python app\content_diff.py --course "X" --write
python app\vault_export.py --course "X"                     # Obsidian
python app\vault_export.py --course "X" --format notion
python app\doctor.py --fix                                 # yt-dlp -U + pip thieu
python app\tools_fix.py --yt-dlp-only
python app\notes.py --course "X" --list
python app\notes.py --course "X" --path "01 - C/01 - L" --set "Ghi chu"
python app\disk_report.py --write
python app\study_plan.py --all --days 14
python app\llm_prompt.py --list-presets
python app\llm_prompt.py --list-providers
python app\llm_prompt.py --check
# Grok (xAI) — console.x.ai
python app\llm_prompt.py --set-key grok "xai-..." --set-model grok grok-3-mini --set-provider grok
python app\llm_prompt.py --course "X" --preset translate_vi --provider grok
# Cac provider khac
python app\llm_prompt.py --set-key openrouter "sk-or-..."
python app\llm_prompt.py --set-key gemini "AIza..." --set-model gemini gemini-2.0-flash
python app\llm_prompt.py --set-key qwen "sk-..." --set-key glm "..." --set-key kimi "..."
python app\llm_prompt.py --set-fallback "grok,openrouter,gemini,qwen,glm,kimi,deepseek,openai,anthropic"
python app\llm_prompt.py --course "X" --source tonghop --preset translate_vi
python app\llm_prompt.py --course "X" --user-prompt "Dich sang tieng Viet, giong trang trong" --provider grok
python app\llm_prompt.py --course "X" --source lesson --lesson "01 - C/01 - L" --preset summary_todo --provider qwen
python app\main.py --course "X" --only transcribe           # phu de chi thieu
python app\main.py --course "X" --index        # build RAG index sau pipeline
python app\export.py   --course "X" --docx     # gộp & xuất Word (Nhóm A)
python app\ai_tools.py --course "X" --translate --summary   # dịch + tóm tắt/to-do (cần API key / deep-translator)
python app\updates.py  --course "X" --scan-local            # sức khỏe local / diff helper
python -m cloud.sync   --course "X"            # sync knowledge (r2|gdrive|onedrive)
python -m cloud.sync   --all                   # sync mọi khóa
python -m cloud.sync   --test                  # thử kết nối provider đang chọn
python -m rag.chat     --course "X" --index    # build catalog + TF-IDF
python -m rag.chat     --course "X" --ask "..." # hỏi đáp RAG
python -m rag.chat     --multi "A,B" --ask "..."
python app\search_lib.py "webhook"             # tìm toàn kho (không cần Claude)
python app\search_lib.py --report              # _Warehouse_Report.md
python app\web_viewer.py                       # http://127.0.0.1:8765
python app\health_check.py --write --notify    # health + ghi file (+ toast Windows)
# Windows lịch hàng ngày:  app\install_health_task.ps1
# macOS launchd:           bash app/install_health_launchd.sh
python app\export_site.py --open               # site tinh offline
python app\tray_app.py                         # system tray (can pystray)
```


Mỗi lần chạy ghi log vào `Archiver\logs\run_<thời gian>.log`. Không truyền `--course` ⇒ dùng `SkoolCourse` (khóa cũ).

---

## 6. Phụ đề chạy ngầm (Whisper) — sống qua reboot / tắt Claude

Engine mặc định **faster-whisper + `distil-large-v3`** (English-only, nhanh & nhẹ; tự dùng GPU NVIDIA nếu có, không thì CPU int8). Xuất `video.txt` + `video.srt` **cùng folder với video**.

**Chạy ngầm bằng Windows Task Scheduler** (độc lập Claude, tự tiếp tục sau khi bật lại máy, xong thì báo Windows):

```powershell
.\install_transcribe_task.cmd -All                       # quét SkoolCourse + mọi courses/*
.\install_transcribe_task.cmd -Course "AI Automations by Jack"
.\uninstall_transcribe_task.cmd                          # gỡ khi xong
```

Cơ chế:
- Chạy ngay + **tự chạy lại mỗi lần đăng nhập** → tắt/mở máy vẫn tiếp tục (bài nào có `.txt` rồi thì bỏ qua).
- Chạy **song song** lúc đang tải: bỏ qua file đang tải dở; **không tự kết thúc khi còn đang tải**.
- Khi transcribe hết & không còn tải → **hiện thông báo Windows** rồi dừng. (Claude tắt vẫn báo, vì đây là task của Windows.)

Chạy tay (không cần task): `.\app\run_transcribe_watch.ps1 --all` (hoặc thêm `--once` để làm 1 lượt rồi thoát).

> Whisper chỉ ra **text đúng ngôn ngữ gốc** (tiếng Anh). Muốn **bản tiếng Việt** dùng nút **📄 Xuất & Báo cáo → 🌐 Dịch tiếng Việt** (xem mục 1b) để dịch file tổng hợp.

---

## 7. Cấu hình ([config.py](app/config.py))

| Khóa | Mặc định | Ý nghĩa |
|------|----------|---------|
| `JS_RUNTIME` | `"node"` | JS runtime cho yt-dlp (vượt chặn bot YouTube). `""` = tắt |
| `ONLY_HOSTS` | `[]` | `["stream.video.skool.com"]` = chỉ tải native |
| `YT_COOKIES_FILE` | `""` | đường dẫn `cookies.txt` (Netscape) nếu cần đăng nhập |
| `YT_COOKIES_BROWSER` | `""` | `"firefox"` (Chrome/Edge bản mới bị App-Bound Encryption — **không dùng được**) |
| `MAX_TRIES` / `RETRY_WAIT` | `6` / `8` | số lần thử lại / giây nghỉ mỗi video |
| `WHISPER_ENGINE` | `"faster-whisper"` | hoặc `"openai-whisper"` |
| `WHISPER_MODEL` | `"distil-large-v3"` | hoặc `"large-v3-turbo"`, `"large-v3"`… |
| `WHISPER_TASK` | `"transcribe"` | `"translate"` = dịch SANG tiếng Anh |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE` | `auto` / `int8` | tự dò GPU; CPU dùng int8 |
| `WATCH_INTERVAL` / `WATCH_MIN_AGE` | `90` / `60` | chu kỳ quét / tuổi tối thiểu của file trước khi transcribe |
| `SKOOL_BASE` *(env)* | *(thư mục cha của Archiver)* | đổi thư mục gốc (không còn hardcode ổ E:) |

---

## 8. Cấu trúc output

```
courses\<Tên khóa>\
├─ _chapters.json, vid__*.json, meta__*.json   ← dump đầu vào
├─ video_audit.txt                              ← báo cáo
├─ _TongHop.md / _TongHop.docx                  ← Gộp & xuất (Nhóm A)
├─ _TongHop.vi.md                               ← bản dịch tiếng Việt
├─ _TomTat.md                                   ← tóm tắt + to-do (AI)
├─ 01 - <Chương>\ 01 - <Bài>\
│  ├─ video.mp4
│  ├─ video.txt / video.srt   (nếu transcribe)
│  ├─ description.md
│  └─ resources\  (_links.txt + file đính kèm)
```

---

## 9. Xử lý sự cố

Khi tải lỗi, pipeline **tự phân loại nguyên nhân và in cách xử lý**, đồng thời gom nhóm ở cuối. Tham chiếu nhanh:

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| *"Sign in to confirm you're not a bot"* (YouTube) | thiếu JS runtime | Cài **Node.js**; tự dùng `--js-runtimes node` |
| `UnicodeEncodeError` / `'charmap'` (ký tự `▶`…) | console Windows cp1252 | Đã xử lý: ép UTF-8 (`run.ps1` + `setup_console`) |
| Native Skool **403 Forbidden** | token **24h hết hạn** | GUI: nút **🔑 Cứu bài native** (tự dump lại token + tải). CLI: dump lại `vid__*.json` → `--only videos --native-only` |
| Resource tải lỗi | link file **8h hết hạn** | Dump lại `meta__*.json` → `--only extras` |
| `Failed to decrypt with DPAPI` | Chrome/Edge mã hóa cookie (ABE) | Đừng dùng `--cookies-browser`; xuất `cookies.txt` → `--cookies-file` |
| ORPHAN trong audit | tên chương/bài đổi giữa 2 lần dump | Chuyển `video.*` về đúng folder, xóa folder thừa, `--only audit` |
| `[!] khong khop folder` (NOFOLDER) | chưa chạy `folders` | Chạy `--only folders` trước |
| Chặn chạy `.ps1` | ExecutionPolicy | Dùng file `.cmd` (đã tự bypass) |
| Transcribe lỗi tải model | mạng/HuggingFace | Watcher tự thử lại; kiểm tra mạng |

---

## 10. Ghi chú bàn giao

- **Bàn giao = zip mỗi thư mục `Archiver\`** (bỏ `__pycache__\`, `logs\`, **`app\.browser\`**, **`app\.settings.json`** — chứa API key). Mọi thứ khác trong `E:\SkoolProject\` là dữ liệu/môi trường, dựng lại được từ `Archiver\` + `setup`.
- **Sang máy khác là KHÔNG có khóa nào.** Khóa đã tải nằm ở `courses\` và `SkoolCourse\` — **ngoài** `Archiver\`. Vì thế zip `Archiver\` không kèm khóa; máy mới mở app thấy danh sách **trống**, tự tải khóa mới. (`app\.browser\` là phiên đăng nhập Skool của bạn — đừng đưa kèm.)
- Muốn dọn khóa ngay trên máy này: dùng nút **🗑 Xóa khóa** ở Bước 1 (mặc định đưa vào **Thùng rác**, khôi phục được).
- **Nguồn chuẩn duy nhất là `Archiver\`.** Script lẻ ở thư mục gốc (`download_videos.py`, `check_video.py`, `make_folder.py`, `save_extras.py`) là **bản cũ standalone đã được gộp** — giữ tham khảo, không cần dùng.
- Quy tắc token: **native 24h · file/resource 8h** → luôn dump & chạy trong ngày.
- Whisper trên CPU rất chậm với khóa lớn (có thể nhiều giờ/ngày). Có GPU NVIDIA → cài `torch`/CUDA để nhanh hơn nhiều.
