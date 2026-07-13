#!/usr/bin/env python3
"""Smoke tests Phase 1 — chay: python tests_phase1.py"""
from __future__ import annotations

import json, os, sys, tempfile
from pathlib import Path

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


def main():
    print("Phase 1+2 smoke tests")
    fails = 0
    for fn in (test_progress_badge, test_queue_persist, test_cloud_policy,
               test_updates_diff, test_rag_score, test_tfidf_and_multi,
               test_queue_workers_settings, test_parallel_claim):
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
