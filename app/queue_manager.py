from collections import deque
from typing import Any
from app.agent import run
from app.exceptions import ScoutFailed, DiskQuotaExceeded
from app.logger import log

Job = tuple[str, str, str, int, str]

_queue: deque[Job] = deque()

def enqueue(category: str, subject: str, action: str, want: int = 1, kind: str = "raw") -> None:
    _queue.append((category, subject, action, want, kind))

def pending() -> int:
    return len(_queue)

def drain() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while _queue:
        job = _queue.popleft()
        category, subject, action, want, kind = job
        try:
            out.extend(run(category, subject, action, want, kind=kind))
        except (ScoutFailed, DiskQuotaExceeded) as e:
            _queue.appendleft(job)
            log(f"file suspendue: {e}")
            break
    return out
