"""Kolejka zadań dla studia: postęp, anulowanie i strumień zdarzeń do przeglądarki.

Każde zadanie biegnie we własnym wątku i rejestruje uruchamiane procesy ffmpeg, więc da się je
przerwać w pół renderu. Zadania z tym samym `slot` wypierają się nawzajem — kolejna zmiana w
inspektorze anuluje poprzedni podgląd zamiast ustawiać się w kolejce.

    queue = JobQueue()
    job = queue.submit("render", lambda ctx: ..., slot="scene:s3")
    for event in queue.stream():  ...        # SSE
"""
from __future__ import annotations

import queue as queuelib
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from . import ffmpeg

_local = threading.local()


class Cancelled(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    kind: str
    slot: str | None = None
    status: str = "queued"          # queued | running | done | error | cancelled
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None
    log: list[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    finished: float | None = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _procs: list[Any] = field(default_factory=list, repr=False)

    def public(self) -> dict:
        return {"id": self.id, "kind": self.kind, "slot": self.slot, "status": self.status,
                "progress": round(self.progress, 3), "message": self.message,
                "result": self.result, "error": self.error, "log": self.log[-40:],
                "created": self.created, "finished": self.finished}

    # --- API dla kodu zadania
    def check(self) -> None:
        if self._cancel.is_set():
            raise Cancelled("przerwane")

    def step(self, progress: float | None = None, message: str | None = None) -> None:
        self.check()
        if progress is not None:
            self.progress = max(0.0, min(1.0, progress))
        if message:
            self.message = message
            self.log.append(message)

    def kill(self) -> None:
        self._cancel.set()
        for proc in list(self._procs):
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass


def current_job() -> Job | None:
    return getattr(_local, "job", None)


def _register(proc) -> None:
    job = current_job()
    if job is None:
        return
    job._procs.append(proc)
    if job._cancel.is_set():
        try:
            proc.kill()
        except Exception:
            pass


def _progress(seconds: float) -> None:
    job = current_job()
    if job is None:
        return
    if job._cancel.is_set():
        for proc in list(job._procs):
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        return
    total = getattr(job, "_expected", None)
    if total:
        job.progress = max(job.progress, min(0.99, seconds / total))


ffmpeg.set_hooks(process=_register, progress=_progress)


class JobQueue:
    def __init__(self, keep: int = 100):
        self.jobs: dict[str, Job] = {}
        self.keep = keep
        self._lock = threading.Lock()
        self._subscribers: list[queuelib.Queue] = []

    # -------------------------------------------------- zdarzenia
    def subscribe(self) -> queuelib.Queue:
        q: queuelib.Queue = queuelib.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queuelib.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event: dict) -> None:
        with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            try:
                q.put_nowait(event)
            except queuelib.Full:
                pass

    # -------------------------------------------------- zadania
    def submit(self, kind: str, fn: Callable[[Job], Any], slot: str | None = None,
               expected: float | None = None) -> Job:
        if slot:
            for other in list(self.jobs.values()):
                if other.slot == slot and other.status in ("queued", "running"):
                    self.cancel(other.id)
        job = Job(id=uuid.uuid4().hex[:8], kind=kind, slot=slot)
        if expected:
            setattr(job, "_expected", expected)
        with self._lock:
            self.jobs[job.id] = job
            if len(self.jobs) > self.keep:
                for old in sorted(self.jobs.values(), key=lambda j: j.created)[: len(self.jobs) - self.keep]:
                    if old.status in ("done", "error", "cancelled"):
                        self.jobs.pop(old.id, None)
        self.publish({"type": "job", "job": job.public()})
        threading.Thread(target=self._run, args=(job, fn), daemon=True).start()
        return job

    def _run(self, job: Job, fn: Callable[[Job], Any]) -> None:
        _local.job = job
        job.status = "running"
        self.publish({"type": "job", "job": job.public()})
        try:
            job.result = fn(job)
            job.status = "cancelled" if job._cancel.is_set() else "done"
            job.progress = 1.0
        except Cancelled:
            job.status = "cancelled"
            job.message = "przerwane"
        except BaseException as exc:            # SystemExit z modułów też łapiemy
            if job._cancel.is_set():
                job.status = "cancelled"
                job.message = "przerwane"
            else:
                job.status = "error"
                job.error = str(exc) or exc.__class__.__name__
                job.log.append(traceback.format_exc()[-1500:])
        finally:
            job.finished = time.time()
            _local.job = None
            self.publish({"type": "job", "job": job.public()})

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status not in ("queued", "running"):
            return False
        job.kill()
        job.status = "cancelled"
        job.message = "przerwane"
        self.publish({"type": "job", "job": job.public()})
        return True

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def listing(self, limit: int = 40) -> list[dict]:
        rows = sorted(self.jobs.values(), key=lambda j: j.created, reverse=True)[:limit]
        return [j.public() for j in rows]

    def stream(self, heartbeat: float = 15.0):
        """Generator zdarzeń Server-Sent Events."""
        q = self.subscribe()
        try:
            yield {"type": "hello", "jobs": self.listing()}
            while True:
                try:
                    yield q.get(timeout=heartbeat)
                except queuelib.Empty:
                    yield {"type": "ping", "t": time.time()}
        finally:
            self.unsubscribe(q)
