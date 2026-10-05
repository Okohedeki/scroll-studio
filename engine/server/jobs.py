"""Background jobs for the server: builds, snapshots and recordings run one at a time on a worker thread
(they share the GPU), with progress and a log tail the UI polls."""
from __future__ import annotations

import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Job:
    id: str
    kind: str
    project: str
    label: str
    status: str = "queued"          # queued | running | done | failed
    progress: float = 0.0
    message: str = ""
    log: list = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None
    created: float = field(default_factory=time.time)
    finished: Optional[float] = None

    def public(self, tail: int = 200) -> dict:
        return {"id": self.id, "kind": self.kind, "project": self.project, "label": self.label, "status": self.status,
                "progress": round(self.progress, 4), "message": self.message, "log": self.log[-tail:],
                "result": self.result, "error": self.error, "created": self.created, "finished": self.finished}


class JobQueue:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.q: "queue.Queue[tuple[Job, Callable]]" = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, kind: str, project: str, label: str, fn: Callable[[Job], Optional[dict]]) -> Job:
        job = Job(id=uuid.uuid4().hex[:10], kind=kind, project=project, label=label)
        self.jobs[job.id] = job
        self.q.put((job, fn))
        return job

    def list(self, project: Optional[str] = None) -> list[dict]:
        js = sorted(self.jobs.values(), key=lambda j: -j.created)
        return [j.public(tail=3) for j in js if project is None or j.project == project][:30]

    def _worker(self):
        while True:
            job, fn = self.q.get()
            job.status = "running"
            try:
                job.result = fn(job) or {}
                job.status = "done"
                job.progress = 1.0
            except Exception as e:  # report, keep the worker alive
                job.status = "failed"
                job.error = str(e)
                job.log.append(traceback.format_exc()[-3000:])
            job.finished = time.time()


def logger(job: Job):
    def log(msg: str):
        for line in str(msg).splitlines():
            job.log.append(line)
        del job.log[:-2000]
    def progress(f: float, msg: str = ""):
        job.progress = max(0.0, min(1.0, f))
        if msg:
            job.message = msg
    return log, progress
