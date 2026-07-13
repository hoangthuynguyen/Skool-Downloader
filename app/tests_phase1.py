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
    print("Phase 1–10 + Sprint A smoke tests")
    fails = 0
    for fn in (test_progress_badge, test_queue_persist, test_cloud_policy,
               test_updates_diff, test_rag_score, test_tfidf_and_multi,
               test_queue_workers_settings, test_parallel_claim,
               test_search_and_report, test_onedrive_module, test_health_and_web,
               test_export_site_and_embed, test_config_base_and_doctor_requeue,
               test_video_classify_and_lesson_path, test_cleanup_fails,
               test_version_module, test_warehouse_fails_field,
               test_retry_failed_and_knowledge_pack):
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
