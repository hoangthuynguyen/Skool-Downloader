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


def requeue_failed(path=None, include_stopped=True):
    """Dua job failed/stopped ve queued. Tra ve so job da requeue."""
    state = load_state(path)
    statuses = {"failed"}
    if include_stopped:
        statuses.add("stopped")
    n = 0
    for j in state.get("jobs") or []:
        if j.get("status") in statuses:
            j["status"] = "queued"
            j["error"] = None
            j["returncode"] = None
            j["started_at"] = None
            j["finished_at"] = None
            n += 1
    if n:
        save_state(state, path)
    return n


def requeue_job(job_id, path=None):
    state = load_state(path)
    for j in state.get("jobs") or []:
        if j.get("id") == job_id and j.get("status") in ("failed", "stopped", "cancelled", "done"):
            j["status"] = "queued"
            j["error"] = None
            j["returncode"] = None
            j["started_at"] = None
            j["finished_at"] = None
            save_state(state, path)
            return True
    return False


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


# Transcribe/kind nang I/O GPU: luon 1 worker. Download co the song song.
SERIAL_KINDS = {"transcribe"}


def load_queue_settings():
    """Doc app/.settings.json -> queue.max_workers (mac dinh 1)."""
    try:
        s = json.loads((HERE / ".settings.json").read_text(encoding="utf-8"))
        q = s.get("queue") or {}
        w = int(q.get("max_workers") or 1)
        return {"max_workers": max(1, min(w, 4))}
    except Exception:
        return {"max_workers": 1}


def save_queue_settings(max_workers=1):
    path = HERE / ".settings.json"
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        s = {}
    s["queue"] = {"max_workers": max(1, min(int(max_workers), 4))}
    path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


class QueueRunner:
    """Chay hang doi. Phase 2: max_workers > 1 -> song song download (subprocess).

    Transcribe van serial (SERIAL_KINDS) de tranh tranh GPU/RAM.
    """

    def __init__(self, state_path=None, on_event=None, py=None, max_workers=None):
        self.state_path = Path(state_path or STATE_FILE)
        self.on_event = on_event or (lambda ev: None)
        self.py = py or PY
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()          # bao ve claim job + state
        self._procs = {}                       # job_id -> Popen
        self.current_id = None                 # job chinh (tuong thich GUI)
        if max_workers is None:
            max_workers = load_queue_settings().get("max_workers", 1)
        self.max_workers = max(1, min(int(max_workers), 4))

    def _emit(self, type_, **kw):
        try:
            self.on_event({"type": type_, **kw})
        except Exception:
            pass

    def stop(self):
        """Dung tat ca job dang chay + khong lay job moi."""
        self._stop.set()
        with self._lock:
            procs = list(self._procs.values())
        for p in procs:
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

    def _claim_next(self, prefer_serial_only=False):
        """Claim 1 job queued -> running (atomic). Tra ve job dict hoac None."""
        with self._lock:
            state = load_state(self.state_path)
            queued = [j for j in state["jobs"] if j.get("status") == "queued"]
            if not queued:
                return None
            queued = sorted(queued, key=lambda j: (j.get("priority", 100), j.get("created_at") or ""))
            for job in queued:
                kind = job.get("kind") or "full"
                is_serial = kind in SERIAL_KINDS
                if prefer_serial_only and not is_serial:
                    continue
                if (not prefer_serial_only) and is_serial:
                    # chi chay serial khi khong con worker khac
                    if any(1 for p in self._procs.values()):
                        continue
                job["status"] = "running"
                job["started_at"] = _now()
                job["error"] = None
                save_state(state, self.state_path)
                return dict(job)
            return None

    def run_all(self, max_jobs=None):
        """Chay het job queued. Song song toi da self.max_workers."""
        from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

        n = 0
        in_flight = {}  # future -> job_id
        workers = self.max_workers
        self._emit("config", max_workers=workers)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            while not self._stop.is_set():
                # do day slot
                while (not self._stop.is_set()
                       and len(in_flight) < workers
                       and (max_jobs is None or n < max_jobs)):
                    # neu dang co serial job -> khong claim them
                    serial_running = False
                    with self._lock:
                        state = load_state(self.state_path)
                        for j in state["jobs"]:
                            if j.get("status") == "running" and (j.get("kind") in SERIAL_KINDS):
                                serial_running = True
                                break
                    if serial_running and in_flight:
                        break
                    job = self._claim_next()
                    if not job:
                        break
                    jid = job["id"]
                    fut = pool.submit(self._run_claimed, job)
                    in_flight[fut] = jid
                    n += 1

                if not in_flight:
                    if not next_queued(load_state(self.state_path)):
                        self._emit("idle")
                    break

                done, _ = wait(in_flight.keys(), timeout=0.4, return_when=FIRST_COMPLETED)
                for fut in done:
                    in_flight.pop(fut, None)
                    try:
                        fut.result()
                    except Exception as e:
                        self._emit("log", job_id="?", line=f"[queue worker] {e}")

        self._emit("finished", ran=n)
        return n

    def _run_claimed(self, job):
        """Chay job da claim (status=running)."""
        job_id = job["id"]
        self.current_id = job_id
        cmd = build_cmd(job, py=self.py)
        self._emit("start", job=dict(job), cmd=cmd)
        log_lines = []
        rc = 1
        proc = None
        try:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            proc = subprocess.Popen(
                cmd, cwd=str(HERE), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=NO_WIN,
            )
            with self._lock:
                self._procs[job_id] = proc
            for line in proc.stdout:
                line = line.rstrip("\n")
                log_lines.append(line)
                if len(log_lines) > 80:
                    log_lines = log_lines[-80:]
                self._emit("log", job_id=job_id, line=line)
                if self._stop.is_set():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break
            rc = proc.wait()
        except Exception as e:
            rc = 1
            log_lines.append(f"[queue] {e}")
            self._emit("log", job_id=job_id, line=f"[queue] {e}")
        finally:
            with self._lock:
                self._procs.pop(job_id, None)
            if self.current_id == job_id:
                self.current_id = None

        with self._lock:
            state = load_state(self.state_path)
            j = next((x for x in state["jobs"] if x["id"] == job_id), None)
            if j:
                j["returncode"] = rc
                j["finished_at"] = _now()
                j["log_tail"] = "\n".join(log_lines[-40:])
                if self._stop.is_set() and rc != 0:
                    j["status"] = "stopped"
                elif rc == 0:
                    j["status"] = "done"
                else:
                    j["status"] = "failed"
                    j["error"] = f"exit {rc}"
                save_state(state, self.state_path)
                self._emit("end", job=dict(j))


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
    ap.add_argument("--workers", type=int, default=None, help="So job song song (1-4). Luu vao settings neu kem --save-workers.")
    ap.add_argument("--save-workers", action="store_true", help="Luu --workers vao .settings.json.")
    ap.add_argument("--status", action="store_true", help="In trang thai queue.")
    ap.add_argument("--clear-done", action="store_true", help="Xoa job done/cancelled/stopped.")
    ap.add_argument("--cancel", help="Huy 1 job queued theo id.")
    ap.add_argument("--remove", help="Xoa job khoi queue theo id.")
    ap.add_argument("--requeue-failed", action="store_true", help="Dua failed/stopped ve queued.")
    a = ap.parse_args()
    if a.workers is not None and a.save_workers:
        save_queue_settings(a.workers); print(f"Saved max_workers={a.workers}")

    if a.clear_done:
        clear_done(); print("Cleared done/cancelled/stopped.")
    if a.requeue_failed:
        n = requeue_failed(); print(f"Requeued {n} job(s).")
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
        runner = QueueRunner(on_event=lambda ev: _cli_event(ev),
                             max_workers=a.workers)
        n = runner.run_all()
        print(f"=== Queue finished ({n} job(s), workers={runner.max_workers}) ===")


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
