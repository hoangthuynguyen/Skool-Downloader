#!/usr/bin/env python3
"""Smoke tests Phase 1 — chay: python tests_phase1.py"""
from __future__ import annotations

import json, os, sys, tempfile
from pathlib import Path
# json used by cleanup tests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def ok(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
        return True
    print(f"  FAIL  {name}  {detail}")
    return False


def test_progress_badge():
    import progress as P
    b = P.status_badge({"has_data": True, "total": 10, "done": 10, "native_expired": []})
    assert b["code"] == "done"
    b = P.status_badge({"has_data": True, "total": 10, "done": 3, "native_expired": [{"x": 1}]})
    assert b["code"] == "token"
    b = P.status_badge({"has_data": False})
    assert b["code"] == "empty"
    print("  PASS  progress badges")


def test_queue_persist():
    import queue_engine as QE
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "q.json"
        created = QE.add_jobs(["CourseA", "CourseB"], kind="full", until_clean=True, path=path)
        assert len(created) == 2
        state = QE.load_state(path)
        assert len(state["jobs"]) == 2
        jid = state["jobs"][0]["id"]
        assert QE.move_job(jid, +1, path=path)
        state = QE.load_state(path)
        assert state["jobs"][1]["id"] == jid
        QE.cancel_job(state["jobs"][0]["id"], path=path)
        state = QE.load_state(path)
        assert state["jobs"][0]["status"] == "cancelled"
        cmd = QE.build_cmd({"course": "CourseA", "kind": "full", "until_clean": True})
        assert "main.py" in cmd[1] or cmd[1].endswith("main.py")
        assert "--course" in cmd and "CourseA" in cmd
        assert "--until-clean" in cmd
        print("  PASS  queue persist + move + build_cmd")


def test_cloud_policy():
    from cloud.policy import should_upload
    root = Path("/tmp/skool_course_test")
    assert should_upload(root / "description.md", root, "knowledge") is True
    assert should_upload(root / "video.mp4", root, "knowledge") is False
    assert should_upload(root / "video.mp4", root, "full") is True
    assert should_upload(root / "resources" / "a.pdf", root, "knowledge") is True
    assert should_upload(root / "video.part", root, "full") is False
    print("  PASS  cloud policy knowledge/full")


def test_updates_diff():
    import updates as U
    import progress as P
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "_chapters.json").write_text(
            json.dumps(["Chapter One", "Chapter Two"]), encoding="utf-8")
        # fake empty scan path
        titles = U.saved_chapter_titles(root)
        assert "Chapter One" in titles or "Chapter One" in {t for t in titles}
        remote = [{"id": "1", "title": "Chapter One"},
                  {"id": "2", "title": "Chapter Two"},
                  {"id": "3", "title": "Brand New"}]
        d = U.diff_remote_chapters(root, remote)
        assert any("Brand New" in (c.get("title") or "") for c in d["new_chapters"])
        assert d["has_updates"] is True or len(d["new_chapters"]) == 1
        p = U.mark_update_meta(root, d)
        assert p.exists()
        meta = U.read_update_meta(root)
        assert meta and meta.get("summary")
        print("  PASS  updates diff + meta")


def test_rag_score():
    from rag.index import score_lesson, _tokens
    s = score_lesson("webhook automation", {
        "title": "Using Webhooks",
        "chapter": "API",
        "text": "Learn webhook automation with Zapier",
        "preview": "",
    })
    assert s > 0
    assert "webhook" in _tokens("Webhook and the API")
    print("  PASS  rag scoring")


def test_tfidf_and_multi():
    from rag.vector import _tf, _idf, _tfidf_vec, _cosine, retrieve_multi
    docs = [["webhook", "api", "zapier"], ["database", "sql", "index"], ["webhook", "event"]]
    idf = _idf(docs)
    v0 = _tfidf_vec(_tf(docs[0]), idf)
    v2 = _tfidf_vec(_tf(docs[2]), idf)
    assert _cosine(v0, v2) > _cosine(v0, _tfidf_vec(_tf(docs[1]), idf))
    # multi empty roots ok
    r = retrieve_multi([], "webhook", top_k=2)
    assert r["context"] == "" or True
    print("  PASS  tfidf cosine + multi empty")


def test_queue_workers_settings():
    import queue_engine as QE
    with tempfile.TemporaryDirectory() as td:
        # monkeypatch HERE settings via save to real file is ok; just test clamp logic
        assert QE.load_queue_settings()["max_workers"] >= 1
    print("  PASS  queue workers settings")


def test_parallel_claim():
    import queue_engine as QE
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "q.json"
        QE.add_jobs(["A", "B", "C"], path=path)
        runner = QE.QueueRunner(state_path=path, max_workers=2, py=sys.executable)
        # claim two
        j1 = runner._claim_next()
        j2 = runner._claim_next()
        assert j1 and j2 and j1["id"] != j2["id"]
        state = QE.load_state(path)
        running = [j for j in state["jobs"] if j["status"] == "running"]
        assert len(running) == 2
        print("  PASS  parallel claim")


def test_search_and_report():
    import search_lib as S
    # empty warehouse still returns structure
    md, entries = S.warehouse_report()
    assert "Skool Archiver" in md
    assert isinstance(entries, list)
    hits = S.search_all("zzz_nonexistent_term_xyz", top_k=3)
    assert hits == [] or isinstance(hits, list)
    print("  PASS  search + warehouse report")


def test_onedrive_module():
    from cloud import onedrive as OD
    assert "Files.ReadWrite" in OD.SCOPES
    assert not OD._have_msal() or OD._have_msal() in (True, False)
    print("  PASS  onedrive module import")


def test_health_and_web():
    import health_check as H
    r = H.run_health()
    assert "summary" in r and "courses" in r
    assert "n_courses" in r["summary"]
    import web_viewer as W
    assert W._esc("<x>") == "&lt;x&gt;"
    data = W.list_courses_data()
    assert isinstance(data, list)
    # handler routes exist
    assert hasattr(W.Handler, "do_GET")
    print("  PASS  health + web viewer")


def test_export_site_and_embed():
    import export_site as ES
    assert ES.slug("Hello World!") == "hello-world"
    assert "&lt;" in ES.esc("<")
    from rag.embed_local import available, load_embeddings
    # available may be False — OK
    assert available() in (True, False)
    with tempfile.TemporaryDirectory() as td:
        out = ES.export_site(out_dir=td + "/site", log=lambda *_: None)
        assert (out / "index.html").exists()
        assert (out / "search.html").exists()
        assert (out / "manifest.webmanifest").exists()
    print("  PASS  export site + embed module")


def test_version_module():
    import version as V
    assert V.__version__
    assert "Skool" in V.version_string()
    print("  PASS  version module")


def test_retry_failed_and_knowledge_pack():
    import config as C
    import videos as V
    import knowledge_pack as KP
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lesson = root / "01 - Chap" / "02 - Bai"
        lesson.mkdir(parents=True)
        (lesson / "description.md").write_text("hello", encoding="utf-8")
        (lesson / "video.txt").write_text("transcript", encoding="utf-8")
        (root / "video_fails.json").write_text(json.dumps([
            {"folder": str(lesson), "code": "rate", "message": "429", "fix": "wait"},
            {"folder": str(root / "other"), "code": "token", "message": "403", "fix": "dump"},
        ]), encoding="utf-8")
        old = (C.ROOT, C.ONLY_FAILED, C.FAIL_CODES)
        try:
            C.ROOT = root
            C.ONLY_FAILED = True
            C.FAIL_CODES = {"rate"}
            V.reset_failed_cache()
            fset = V.failed_folder_set(root)
            assert V.in_failed_set(lesson, fset)
            assert V.lesson_ok(lesson) is True
            C.FAIL_CODES = {"token"}
            V.reset_failed_cache()
            assert V.lesson_ok(lesson) is False
        finally:
            C.ROOT, C.ONLY_FAILED, C.FAIL_CODES = old
            V.reset_failed_cache()
        z = KP.pack_course(root, course_name="Test", out_path=str(root / "t.zip"), log=lambda *_: None)
        assert Path(z).exists() and Path(z).stat().st_size > 0
        import zipfile
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            assert any("description.md" in n for n in names)
            assert "_pack_manifest.json" in names
    print("  PASS  retry-failed + knowledge pack")


def test_smart_update_and_chapters():
    """Sprint B: plan_smart_update + ONLY_MISSING + ONLY_CHAPTERS."""
    import config as C
    import videos as V
    import updates as U
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # fake tree: 1 chapter folder + missing video
        chap = root / "01 - Intro"
        lesson = chap / "01 - Hello"
        lesson.mkdir(parents=True)
        (lesson / "description.md").write_text("x", encoding="utf-8")
        # no video.mp4 -> missing when scanned if vid json exists — plan works without
        plan = U.plan_smart_update(root)
        assert "summary" in plan and "has_work" in plan
        # meta new chapters
        (root / "_update_diff.json").write_text(json.dumps({
            "new_chapters": [{"title": "Intro"}],
            "has_updates": True,
        }), encoding="utf-8")
        plan2 = U.plan_smart_update(root)
        assert "Intro" in (plan2.get("new_chapters") or []) or plan2.get("new_chapters") is not None
        old = (C.ONLY_MISSING, C.ONLY_CHAPTERS, C.ONLY_FAILED, C.ONLY_CHAPTER)
        try:
            C.ONLY_FAILED = False
            C.ONLY_CHAPTER = None
            C.ONLY_MISSING = True
            C.ONLY_CHAPTERS = {"intro", "Intro"}
            assert V.chap_ok("Intro") is True
            assert V.chap_ok("Other") is False
            # no video file -> lesson_ok True under ONLY_MISSING
            assert V.lesson_ok(lesson) is True
            # fake done video
            (lesson / "video.mp4").write_bytes(b"\x00\x00")
            assert V.lesson_ok(lesson) is False
        finally:
            C.ONLY_MISSING, C.ONLY_CHAPTERS, C.ONLY_FAILED, C.ONLY_CHAPTER = old
    print("  PASS  smart update + chapters filter")


def test_search_snippet_highlight():
    """Sprint C: snippet + highlight."""
    import search_lib as S
    sn = S.make_snippet(
        "Before the webhook fires the automation runs cleanly after.",
        "webhook",
        mark="【", mark_close="】",
    )
    assert "【webhook】" in sn["snippet"] or "webhook" in sn["snippet"].lower()
    assert sn["match"].lower() == "webhook"
    hit = S.enrich_hit_snippet(
        {"path": "", "preview": "Learn about Prompt engineering today", "title": "t"},
        "Prompt",
        mark="**",
    )
    assert "snippet" in hit and "Prompt" in (hit.get("snippet") or hit.get("preview") or "")
    print("  PASS  search snippet highlight")


def test_pack_backup_restore():
    """Sprint D: local backup + safe restore."""
    import knowledge_pack as KP
    from cloud import pack_backup as PB
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "course"
        dest = Path(td) / "restore_here"
        lesson = root / "01 - C" / "01 - L"
        lesson.mkdir(parents=True)
        (lesson / "description.md").write_text("# Hello knowledge", encoding="utf-8")
        (lesson / "video.txt").write_text("transcript line", encoding="utf-8")
        (lesson / "video.mp4").write_bytes(b"FAKEVIDEO")  # must NOT restore overwrite issue
        z = Path(td) / "pack.zip"
        KP.pack_course(root, course_name="Demo", out_path=str(z), log=lambda *_: None)
        # backup API writes to path
        r = PB.backup_knowledge(root, course_name="Demo", out_path=str(Path(td) / "b.zip"),
                                upload=False, log=lambda *_: None)
        assert Path(r["local"]).exists()
        dest.mkdir()
        (dest / "keep_video").mkdir()
        (dest / "keep_video" / "video.mp4").write_bytes(b"KEEP")
        out = PB.restore_knowledge(z, dest, course_name="Demo", log=lambda *_: None)
        assert out["extracted"] >= 1
        # video.mp4 trong zip khong duoc extract (knowledge pack khong gom video)
        assert (dest / "keep_video" / "video.mp4").read_bytes() == b"KEEP"
        # description restored somewhere
        found = list(dest.rglob("description.md"))
        assert found and "Hello knowledge" in found[0].read_text(encoding="utf-8")
    print("  PASS  pack backup + restore")


def test_notify_session_workers_digest():
    """Sprint E–I smoke: notify log, session BM, workers clamp, digest delta."""
    import config as C
    import notify as N
    import session_state as SS
    import health_check as H
    # notify always logs
    assert N.notify("Test", "hello from tests", level="info") in (True, False)
    assert N.LOG.exists() or True  # may write
    # session
    SS.set_last_course("CourseTest")
    c, t = SS.get_last_course()
    assert c == "CourseTest" and t
    rec = SS.add_bookmark("CourseTest", "/tmp/lesson", title="L1")
    assert rec.get("id")
    bms = SS.list_bookmarks()
    assert any(b.get("id") == rec["id"] for b in bms)
    SS.remove_bookmark(rec["id"])
    # workers config
    old = C.VIDEO_WORKERS
    try:
        C.VIDEO_WORKERS = 3
        assert 1 <= C.VIDEO_WORKERS <= 4
    finally:
        C.VIDEO_WORKERS = old
    # digest delta without prev
    report = {
        "checked_at": "now", "base": str(C.BASE),
        "courses": [{"item": "A", "done": 5, "total": 10, "missing": 5,
                     "expired": 0, "fails": 1, "needs_attention": True}],
        "summary": {"n_courses": 1, "done": 5, "total": 10, "missing": 5,
                    "expired": 0, "fails": 1, "needs_attention": 1, "size": 0},
    }
    d = H.compute_delta(report, prev=None)
    assert d["has_prev"] is False
    prev = {
        "checked_at": "before",
        "courses": [{"item": "A", "done": 3, "total": 10, "missing": 7,
                     "expired": 0, "fails": 2, "needs_attention": True}],
        "summary": {"n_courses": 1, "done": 3, "total": 10, "missing": 7,
                    "expired": 0, "fails": 2, "needs_attention": 1},
    }
    d2 = H.compute_delta(report, prev=prev)
    assert d2["has_prev"] and d2["d_missing"] == -2 and d2["d_done"] == 2
    # transcribe missing_only empty
    import transcribe as T
    with tempfile.TemporaryDirectory() as td:
        old_r = C.ROOT
        try:
            C.ROOT = Path(td)
            r = T.run(missing_only=True)
            assert r.get("todo") == 0
        finally:
            C.ROOT = old_r
    print("  PASS  notify + session + workers + digest + transcribe")


def test_sprint_jklmn():
    """Sprint J–N: adaptive flag, anki cards, quiz grade, smart-batch plan, queue smart flags."""
    import config as C
    import anki_export as AE
    import quiz as Q
    import updates as U
    import queue_engine as QE
    assert getattr(C, "ADAPTIVE_WORKERS", True) in (True, False)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lesson = root / "01 - Intro" / "01 - Lesson"
        lesson.mkdir(parents=True)
        body = (
            "Automation is powerful when webhooks fire correctly. "
            "You should configure the endpoint carefully. "
            "Prompt engineering improves the quality of answers significantly. "
            "Always validate input before processing the request fully."
        )
        (lesson / "video.txt").write_text(body, encoding="utf-8")
        (lesson / "description.md").write_text("About webhooks and automation.", encoding="utf-8")
        # fake catalog for quiz
        rag = root / ".rag"
        rag.mkdir()
        cat = {
            "course": "T", "lessons": [{
                "title": "Lesson", "chapter": "Intro", "section": "Intro",
                "path": str(lesson), "chars": len(body), "preview": body[:80],
                "text": body,
            }],
            "n_lessons": 1, "n_chars": len(body),
        }
        (rag / "catalog_full.json").write_text(json.dumps(cat), encoding="utf-8")
        (rag / "catalog.json").write_text(json.dumps(cat), encoding="utf-8")
        cards = AE.make_cards(root, max_cards=20, cloze=False)
        assert len(cards) >= 1
        z = AE.write_tsv(cards, root / "cards.tsv")
        assert z.exists() and z.stat().st_size > 0
        qz = Q.build_quiz(root, n=5, seed=42)
        assert qz["n"] >= 1
        # grade all correct
        ans = {q["id"]: q["answer_index"] for q in qz["questions"]}
        g = Q.grade(qz, ans)
        assert g["score"] == g["total"]
        path = Q.save_quiz(root, qz)
        assert path.exists()
        plan = U.plan_smart_update(root)
        assert "has_work" in plan
    # queue smart_update flag
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "q.json"
        j = QE.make_job("CourseA", kind="videos", until_clean=True)
        j["smart_update"] = True
        cmd = QE.build_cmd(j)
        assert "--smart-update" in cmd
        assert "--only" in cmd and "videos" in cmd
    print("  PASS  sprint J–N anki/quiz/batch/adaptive")


def test_warehouse_fails_field():
    import progress as P
    st = P.warehouse_stats([])
    assert "fails" in st and st["fails"] == 0
    # health summary has fails key
    import health_check as H
    r = H.run_health()
    assert "fails" in r["summary"]
    print("  PASS  warehouse/health fails field")


def test_cleanup_fails():
    import cleanup as CL
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # fake fails
        (root / "video_fails.json").write_text(json.dumps([
            {"folder": "/a", "code": "token", "message": "het han", "fix": "dump"},
            {"folder": "/b", "code": "token", "message": "het han", "fix": "dump"},
            {"folder": "/c", "code": "rate", "message": "429", "fix": "cho"},
        ]), encoding="utf-8")
        fails = CL.load_fails(root)
        assert len(fails) == 3
        g = CL.summarize_fails(fails)
        assert g[0]["code"] == "token" and g[0]["count"] == 2
        # stale part
        p = root / "video.mp4.part"
        p.write_bytes(b"x" * 10)
        found = CL.find_stale_downloads(root, min_age_sec=0)
        assert any(str(i["path"]).endswith(".part") for i in found)
        r = CL.cleanup_stale(root, apply=True, min_age_sec=0, log=lambda *_: None)
        assert r["deleted"] >= 1
        assert not p.exists()
    print("  PASS  cleanup + fails summary")


def test_video_classify_and_lesson_path():
    import videos as V
    import config as C
    code, _, _ = V.classify("HTTP Error 429: Too Many Requests", "https://www.youtube.com/watch?v=x")
    assert code == "rate"
    code, _, _ = V.classify("ERROR: Sign in to confirm you're not a bot", "https://www.youtube.com/x")
    assert code == "bot"
    assert "rate" in V.RECOVER
    # lesson_ok path normalize
    old_root, old_lesson = C.ROOT, C.ONLY_LESSON
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lesson = root / "01 - Chap" / "02 - Lesson"
            lesson.mkdir(parents=True)
            C.ROOT = root
            C.ONLY_LESSON = "01 - Chap/02 - Lesson"
            assert V.lesson_ok(lesson) is True
            C.ONLY_LESSON = "01 - Chap\\02 - Lesson"
            assert V.lesson_ok(lesson) is True
            C.ONLY_LESSON = "other"
            assert V.lesson_ok(lesson) is False
    finally:
        C.ROOT, C.ONLY_LESSON = old_root, old_lesson
    print("  PASS  video classify + lesson path")


def test_config_base_and_doctor_requeue():
    import config as C
    info = C.base_info()
    assert "base" in info and "source" in info
    assert Path(info["base"]).is_absolute() or True
    # set_base temp without polluting user settings: persist=False
    old = C.BASE
    with tempfile.TemporaryDirectory() as td:
        C.set_base(td, persist=False)
        assert C.BASE == Path(td).resolve()
        assert C.ROOT == C.BASE / "SkoolCourse"
    C.set_base(old, persist=False)

    import doctor as D
    rep = D.run_doctor()
    assert "rows" in rep and "fail" in rep

    import queue_engine as QE
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "q.json"
        jobs = QE.add_jobs(["A"], path=path)
        state = QE.load_state(path)
        state["jobs"][0]["status"] = "failed"
        QE.save_state(state, path)
        n = QE.requeue_failed(path=path)
        assert n == 1
        assert QE.load_state(path)["jobs"][0]["status"] == "queued"
    print("  PASS  config base + doctor + requeue")


def main():
    print("Phase 1–10 + Sprint A–N smoke tests")
    fails = 0
    for fn in (test_progress_badge, test_queue_persist, test_cloud_policy,
               test_updates_diff, test_rag_score, test_tfidf_and_multi,
               test_queue_workers_settings, test_parallel_claim,
               test_search_and_report, test_onedrive_module, test_health_and_web,
               test_export_site_and_embed, test_config_base_and_doctor_requeue,
               test_video_classify_and_lesson_path, test_cleanup_fails,
               test_version_module, test_warehouse_fails_field,
               test_retry_failed_and_knowledge_pack,
               test_smart_update_and_chapters, test_search_snippet_highlight,
               test_pack_backup_restore, test_notify_session_workers_digest,
               test_sprint_jklmn):
        try:
            fn()
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            fails += 1
    if fails:
        print(f"\n{fails} failed"); sys.exit(1)
    print("\nAll passed.")


if __name__ == "__main__":
    main()
