import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from app.database import register_task, update_status, is_duplicate, set_meta
from app.exceptions import DownloadFailed, QualityRejected, ScoutFailed
from app.settings import ROOT, settings
from app.guard import network_delay
from app.health_check import check
from app.downloader import download
from app.inspector import inspect
from app.logger import log
from app.profiler import validate
from app.scout_router import find_candidates

BOT_MARKER = "confirm you’re not a bot"

@dataclass
class Outcome:
    video_id: str
    status: str
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.status == "ok"

def _min_duration(category: str) -> int | None:
    from app.profiler import load_rules
    return load_rules()["categories"][category].get("min_duration_sec")

def _thresholds(category: str, kind: str = "raw", action: str = "") -> tuple[float | None, int | None]:
    if kind != "raw":
        return 0, 0
    r = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))["categories"][category]
    fps = r.get("action_min_fps", {}).get(action, r.get("min_fps"))
    kbps = r.get("action_min_kbps", {}).get(action, r.get("min_kbps"))
    return fps, kbps

def _min_height(category: str, kind: str = "raw") -> int | None:
    if kind != "raw":
        return None
    r = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))["categories"][category]
    return r.get("min_height")

def _max_duration(category: str, kind: str = "raw") -> int | None:
    if kind == "pack":
        return None
    r = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))["categories"][category]
    return r.get("max_duration_sec")

def _is_bot_check(err: Exception) -> bool:
    return BOT_MARKER in str(err) or "confirm you're not a bot" in str(err)

def process(candidate: dict[str, Any], category: str, subject: str, action: str, kind: str = "raw") -> Outcome:
    vid = candidate["video_id"]
    subject = subject.strip().lower()
    action = action.strip().lower()
    if is_duplicate(vid):
        return Outcome(vid, "duplicate", "déjà en base")
    register_task(vid, category, subject, action, candidate["url"], kind)
    set_meta(vid, candidate.get("title"), candidate.get("channel"))
    try:
        meta = inspect(candidate["url"], *_thresholds(category, kind, action), min_height=_min_height(category, kind), min_duration=_min_duration(category), max_duration=_max_duration(category, kind))
    except QualityRejected as e:
        set_meta(vid, e.title or candidate.get("title"), e.channel or candidate.get("channel"))
        update_status(vid, "rejected_inspect", reason=str(e)[:300])
        log(f"{vid} rejeté (inspect): {e}")
        return Outcome(vid, "rejected_inspect", str(e)[:300])
    except DownloadFailed as e:
        if _is_bot_check(e):
            update_status(vid, "pending")
            raise ScoutFailed("bot check YouTube: cookies expirés") from e
        update_status(vid, "failed", reason=str(e)[:300])
        log(f"{vid} inspect échec: {e}")
        return Outcome(vid, "failed", str(e)[:300])
    set_meta(vid, meta.get("title"), meta.get("channel"))
    tbr = round(meta["tbr"]) if meta.get("tbr") else None
    path = None
    last_err = ""
    for attempt in (1, 2):
        try:
            path = download(meta, category, kind, subject, action)
            break
        except DownloadFailed as e:
            if _is_bot_check(e):
                update_status(vid, "pending")
                raise ScoutFailed("bot check YouTube: cookies expirés") from e
            last_err = str(e)[:300]
            log(f"{vid} download échec ({attempt}/2): {e}")
            if attempt == 1:
                network_delay()
    if path is None:
        update_status(vid, "failed", reason=last_err)
        return Outcome(vid, "failed", last_err)
    update_status(vid, "downloaded", file_path=str(path))
    try:
        report = check(path, *_thresholds(category, kind, action))
    except QualityRejected as e:
        path.unlink(missing_ok=True)
        update_status(vid, "rejected_quality", reason=str(e)[:300])
        log(f"{vid} rejeté (qualité): {e} (tbr={tbr})")
        return Outcome(vid, "rejected_quality", str(e)[:300])
    update_status(vid, "ok", file_path=str(path), fps=report["fps"], bitrate=report["kbps"])
    log(f"{vid} OK {report} tbr={tbr}")
    return Outcome(vid, "ok", data={"video_id": vid, "path": str(path), **report})

def run(category: str, subject: str, action: str, want: int = 1, scan: int = 8, kind: str = "raw") -> list[dict[str, Any]]:
    validate(category, action)
    if kind == "edit":
        want = min(want, settings.max_edit_per_job)
    results: list[dict[str, Any]] = []
    for cand in find_candidates(category, subject, action, scan, kind):
        if len(results) >= want:
            break
        res = process(cand, category, subject, action, kind)
        if res:
            results.append(res.data)
        network_delay()
    return results
