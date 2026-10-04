import os
from collections import deque
from datetime import datetime
from pathlib import Path

_LOG_BUFFER: deque[str] = deque(maxlen=200)
_LOG_FILE: Path = Path(__file__).resolve().parent.parent / "logs" / "agent.log"
_MAX_BYTES: int = 1_000_000

def _write(line: str) -> None:
    try:
        if _LOG_FILE.exists() and _LOG_FILE.stat().st_size > _MAX_BYTES:
            _LOG_FILE.replace(_LOG_FILE.with_suffix(".log.1"))
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

def log(message: str, level: str = "INFO") -> None:
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {level} — {message}"
    _LOG_BUFFER.append(entry)
    print(entry)
    _write(f"{entry} (pid {os.getpid()})")

def get_logs() -> list[str]:
    return list(_LOG_BUFFER)
