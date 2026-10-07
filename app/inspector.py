from typing import Any
import yt_dlp
from app.settings import settings
from app.guard import build_ydl_opts
from app.exceptions import QualityRejected, DownloadFailed

def fetch_info(url: str) -> dict[str, Any]:
    opts = {**build_ydl_opts(), "skip_download": True, "quiet": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadFailed(str(e)) from e

def best_video_format(info: dict[str, Any]) -> dict[str, Any]:
    fmts = [
        f for f in info.get("formats", [])
        if f.get("vcodec") not in (None, "none")
        and f.get("height")
        and not (f.get("vcodec") or "").startswith("av01")
        and "m3u8" not in (f.get("protocol") or "")
        and f["height"] <= settings.max_video_height
    ]
    if not fmts:
        raise QualityRejected("aucun format vidéo")
    def codec_rank(f: dict[str, Any]) -> int:
        v = f.get("vcodec") or ""
        return 2 if v.startswith("avc1") else 1 if v.startswith("vp9") else 0
    return max(fmts, key=lambda f: (f["height"], f.get("fps") or 0, codec_rank(f), f.get("tbr") or 0))

def _evaluate(info: dict[str, Any], min_fps: float | None = None, min_kbps: int | None = None, min_height: int | None = None, min_duration: int | None = None, max_duration: int | None = None) -> dict[str, Any]:
    if info.get("live_status") in {"is_live", "is_upcoming"}:
        raise QualityRejected("live/upcoming")
    dur = int(info.get("duration") or 0)
    cap = settings.max_video_duration_sec if max_duration is None else min(max_duration, settings.max_video_duration_sec)
    if not (settings.min_video_duration_sec if min_duration is None else min_duration) <= dur <= cap:
        raise QualityRejected(f"durée {dur}s hors bornes")
    fmt = best_video_format(info)
    if fmt["height"] < (settings.min_video_height if min_height is None else min_height):
        raise QualityRejected(f"hauteur {fmt['height']}p")
    fps = float(fmt.get("fps") or 0)
    if fps < (min_fps if min_fps is not None else settings.min_video_fps) - 1:
        raise QualityRejected(f"fps {fps}")
    tbr = fmt.get("tbr")
    if min_kbps and tbr and tbr < min_kbps - 90:
        raise QualityRejected(f"bitrate estimé {int(tbr)}kbps < {min_kbps}")
    return {
        "video_id": info["id"],
        "title": info["title"],
        "duration": dur,
        "height": fmt["height"],
        "fps": fps,
        "format_id": fmt["format_id"],
        "tbr": fmt.get("tbr"),
        "url": info["webpage_url"],
        "channel": info.get("channel") or info.get("uploader"),
    }

def inspect(url: str, min_fps: float | None = None, min_kbps: int | None = None, min_height: int | None = None, min_duration: int | None = None, max_duration: int | None = None) -> dict[str, Any]:
    info = fetch_info(url)
    try:
        return _evaluate(info, min_fps, min_kbps, min_height, min_duration, max_duration)
    except QualityRejected as e:
        e.title = info.get("title")
        e.channel = info.get("channel") or info.get("uploader")
        raise
