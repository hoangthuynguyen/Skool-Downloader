#!/usr/bin/env python3
"""
Hang doi multi-course (S2).

Moi job chay bang subprocess main.py (cach ly config.C, crash 1 job khong giet app).
Trang thai luu app/queue_state.json -> song qua restart.

  python queue_engine.py --add "Khoa A" --add "Khoa B"
  python queue_engine.py --run
  python queue_engine.py --status
  python queue_engine.py --clear-done
"""
from __future__ import annotations

import argparse, json, os, subprocess, sys, threading, time, uuid
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "queue_state.json"
PY = sys.executable.replace("pythonw.exe", "python.exe")
NO_WIN = 0x08000000 if os.name == "nt" else 0

# kind -> args bo sung cho main.py (sau --course)
KINDS = {
    "full": [],
    "videos": ["--only", "videos"],
    "extras": ["--only", "extras"],
    "transcribe": ["--only", "transcribe"],
    "audit": ["--only", "audit"],
    "native": ["--only", "videos", "--native-only"],
}

STATUSES = ("queued", "running", "done", "failed", "stopped", "cancelled")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_state():
    return {"version": 1, "jobs": [], "updated_at": _now()}


def load_state(path=None):
    path = Path(path or STATE_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data.get("jobs"), list):
            return _default_state()
        return data
    except Exception:
        return _default_state()


def save_state(state, path=None):
    path = Path(path or STATE_FILE)
    state = dict(state)
    state["updated_at"] = _now()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def make_job(course, kind="full", until_clean=True, chapter=None, lesson=None,
             priority=100, label=None):
    """course=None -> layout cu SkoolCourse; str -> courses/<name>."""
    kind = kind or "full"
    if kind not in KINDS and kind != "custom":
        kind = "full"
    jid = uuid.uuid4().hex[:10]
    return {
        "id": jid,
        "course": course,                 # None | str
        "kind": kind,
        "until_clean": bool(until_clean),
        "chapter": chapter,
        "lesson": lesson,
        "priority": int(priority),
        "label": label or _job_label(course, kind, chapter, lesson),
        "status": "queued",
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "returncode": None,
        "error": None,
        "log_tail": "",
    }


def _job_label(course, kind, chapter=None, lesson=None):
    name = course or "SkoolCourse"
    if lesson:
        return f"{name} · bài"
    if chapter:
        return f"{name} · chương {chapter}"
    return f"{name} · {kind}"


def build_cmd(job, py=None):
    """Tao argv de spawn subprocess main.py."""
    py = py or PY
    cmd = [py, str(HERE / "main.py")]
    if job.get("course"):
        cmd += ["--course", job["course"]]
    kind = job.get("kind") or "full"
    cmd += list(KINDS.get(kind, []))
    if job.get("chapter"):
        if "--only" not in cmd:
            cmd += ["--only", "videos"]
        cmd += ["--chapter", job["chapter"]]
    if job.get("lesson"):
        if "--only" not in cmd:
            cmd += ["--only", "videos"]
        cmd += ["--lesson", job["lesson"]]
    if job.get("until_clean") and kind in ("full", "videos", "native"):
        cmd.append("--until-clean")
    return cmd


def add_jobs(courses, kind="full", until_clean=True, path=None):
    """Them nhieu khoa vao queue. courses: list[str|None]. Tra ve list job moi."""
    state = load_state(path)
    created = []
    for c in courses:
        j = make_job(c if c else None, kind=kind, until_clean=until_clean)
        state["jobs"].append(j)
        created.append(j)
    save_state(state, path)
    return created


def add_job(job, path=None):
    state = load_state(path)
    state["jobs"].append(job)
    save_state(state, path)
    return job


def remove_job(job_id, path=None):
    state = load_state(path)
    state["jobs"] = [j for j in state["jobs"] if j.get("id") != job_id]
    save_state(state, path)


def clear_done(path=None):
    state = load_state(path)
    state["jobs"] = [j for j in state["jobs"]
                     if j.get("status") not in ("done", "cancelled", "stopped")]
    save_state(state, path)


def cancel_job(job_id, path=None):
    state = load_state(path)
    for j in state["jobs"]:
        if j.get("id") == job_id and j.get("status") == "queued":
            j["status"] = "cancelled"
            j["finished_at"] = _now()
    save_state(state, path)


def reorder(job_ids, path=None):
    """Sap xep lai: job_ids = thu tu id muon; job khong co trong list giu sau."""
    state = load_state(path)
    by_id = {j["id"]: j for j in state["jobs"]}
    ordered = [by_id[i] for i in job_ids if i in by_id]
    rest = [j for j in state["jobs"] if j["id"] not in set(job_ids)]
    state["jobs"] = ordered + rest
    # cap nhat priority theo thu tu
    for i, j in enumerate(state["jobs"]):
        j["priority"] = i
    save_state(state, path)


def move_job(job_id, delta, path=None):
    """Doi cho job trong danh sach: delta=-1 len, +1 xuong. Tra ve True neu doi duoc."""
    state = load_state(path)
    jobs = state.get("jobs") or []
    idx = next((i for i, j in enumerate(jobs) if j.get("id") == job_id), None)
    if idx is None:
        return False
    new_idx = idx + int(delta)
    if new_idx < 0 or new_idx >= len(jobs):
        return False
    jobs[idx], jobs[new_idx] = jobs[new_idx], jobs[idx]
    for i, j in enumerate(jobs):
        j["priority"] = i
    state["jobs"] = jobs
    save_state(state, path)
    return True


def next_queued(state):
    queued = [j for j in state["jobs"] if j.get("status") == "queued"]
    if not queued:
        return None
    return sorted(queued, key=lambda j: (j.get("priority", 100), j.get("created_at") or ""))[0]


def summary(state=None):
    state = state or load_state()
    counts = {s: 0 for s in STATUSES}
    for j in state.get("jobs") or []:
        st = j.get("status") or "queued"
        counts[st] = counts.get(st, 0) + 1
    return counts


class QueueRunner:
    """Chay tuan tu cac job queued. GUI / CLI dung chung."""

    def __init__(self, state_path=None, on_event=None, py=None):
        self.state_path = Path(state_path or STATE_FILE)
        self.on_event = on_event or (lambda ev: None)
        self.py = py or PY
        self._stop = threading.Event()
        self._proc = None
        self._thread = None
        self.current_id = None

    def _emit(self, type_, **kw):
        try:
            self.on_event({"type": type_, **kw})
        except Exception:
            pass

    def stop(self):
        """Dung job dang chay + khong lay job moi."""
        self._stop.set()
        p = self._proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def start_async(self):
        if self.is_running():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self.run_all, daemon=True)
        self._thread.start()
        return True

    def run_all(self, max_jobs=None):
        """Chay het job queued (hoac toi da max_jobs)."""
        n = 0
        while not self._stop.is_set():
            state = load_state(self.state_path)
            job = next_queued(state)
            if not job:
                self._emit("idle")
                break
            if max_jobs is not None and n >= max_jobs:
                break
            self._run_one(job["id"])
            n += 1
        self._emit("finished", ran=n)
        return n

    def _run_one(self, job_id):
        state = load_state(self.state_path)
        job = next((j for j in state["jobs"] if j["id"] == job_id), None)
        if not job or job.get("status") != "queued":
            return
        job["status"] = "running"
        job["started_at"] = _now()
        job["error"] = None
        save_state(state, self.state_path)
        self.current_id = job_id
        cmd = build_cmd(job, py=self.py)
        self._emit("start", job=dict(job), cmd=cmd)
        log_lines = []
        rc = 1
        try:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            self._proc = subprocess.Popen(
                cmd, cwd=str(HERE), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=NO_WIN,
            )
            for line in self._proc.stdout:
                line = line.rstrip("\n")
                log_lines.append(line)
                if len(log_lines) > 80:
                    log_lines = log_lines[-80:]
                self._emit("log", job_id=job_id, line=line)
                if self._stop.is_set():
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                    break
            rc = self._proc.wait()
        except Exception as e:
            rc = 1
            log_lines.append(f"[queue] {e}")
            self._emit("log", job_id=job_id, line=f"[queue] {e}")
        finally:
            self._proc = None
            self.current_id = None

        state = load_state(self.state_path)
        job = next((j for j in state["jobs"] if j["id"] == job_id), None)
        if not job:
            return
        job["returncode"] = rc
        job["finished_at"] = _now()
        job["log_tail"] = "\n".join(log_lines[-40:])
        if self._stop.is_set() and rc != 0:
            job["status"] = "stopped"
        elif rc == 0:
            job["status"] = "done"
        else:
            job["status"] = "failed"
            job["error"] = f"exit {rc}"
        save_state(state, self.state_path)
        self._emit("end", job=dict(job))


def print_status(path=None):
    state = load_state(path)
    counts = summary(state)
    print(f"Queue ({STATE_FILE.name}): {counts}")
    for j in state.get("jobs") or []:
        c = j.get("course") or "SkoolCourse"
        print(f"  [{j.get('status'):9}] {j.get('id')}  {j.get('label') or c}  kind={j.get('kind')}")


def main():
    ap = argparse.ArgumentParser(description="Skool Archiver multi-course queue")
    ap.add_argument("--add", action="append", default=[], help="Them khoa vao queue (ten duoi courses/). Co the lap.")
    ap.add_argument("--add-legacy", action="store_true", help="Them SkoolCourse (layout cu).")
    ap.add_argument("--kind", default="full", choices=list(KINDS.keys()), help="Loai job.")
    ap.add_argument("--no-until-clean", action="store_true", help="Tat --until-clean.")
    ap.add_argument("--run", action="store_true", help="Chay het job dang queued.")
    ap.add_argument("--status", action="store_true", help="In trang thai queue.")
    ap.add_argument("--clear-done", action="store_true", help="Xoa job done/cancelled/stopped.")
    ap.add_argument("--cancel", help="Huy 1 job queued theo id.")
    ap.add_argument("--remove", help="Xoa job khoi queue theo id.")
    a = ap.parse_args()

    if a.clear_done:
        clear_done(); print("Cleared done/cancelled/stopped.")
    if a.cancel:
        cancel_job(a.cancel); print(f"Cancelled {a.cancel}")
    if a.remove:
        remove_job(a.remove); print(f"Removed {a.remove}")
    if a.add or a.add_legacy:
        courses = list(a.add)
        if a.add_legacy:
            courses.append(None)
        created = add_jobs(courses, kind=a.kind, until_clean=not a.no_until_clean)
        print(f"Added {len(created)} job(s).")
    if a.status or not any([a.add, a.add_legacy, a.run, a.clear_done, a.cancel, a.remove]):
        print_status()
    if a.run:
        runner = QueueRunner(on_event=lambda ev: _cli_event(ev))
        n = runner.run_all()
        print(f"=== Queue finished ({n} job(s)) ===")


def _cli_event(ev):
    t = ev.get("type")
    if t == "start":
        j = ev["job"]
        print(f"\n>>> START {j.get('label')}  ({j.get('id')})")
        print("    ", " ".join(ev.get("cmd") or []))
    elif t == "log":
        print(ev.get("line") or "")
    elif t == "end":
        j = ev["job"]
        print(f"<<< END {j.get('status')}  rc={j.get('returncode')}")
    elif t == "idle":
        print("(queue empty)")


if __name__ == "__main__":
    main()
