from pathlib import Path
from typing import Any
import yt_dlp
from app.settings import settings
from app.guard import build_ydl_opts, check_disk
from app.exceptions import DownloadFailed
from app.logger import log
from app.slug import slug

def _selectors(format_id: str) -> list[str]:
    h = settings.max_video_height
    return [
        f"{format_id}+bestaudio[ext=m4a]/{format_id}+bestaudio",
        f"bv*[height<={h}][vcodec^=avc1][protocol^=https]+ba[ext=m4a]/bv*[height<={h}][vcodec!^=av01][protocol^=https]+ba/b[height<={h}]",
    ]

def _opts(selector: str, out_dir: Path, retries: int = 3, name: str = "") -> dict[str, Any]:
    return {
        **build_ydl_opts(),
        "format": selector,
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / f"{name}__%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "retries": retries,
        "fragment_retries": retries,
        "extractor_retries": 2,
    }

def download(meta: dict[str, Any], category: str, kind: str = "raw", subject: str = "manual", action: str = "manual") -> Path:
    check_disk()
    parts = [slug(subject), slug(action)]
    if parts == ["manual", "manual"]:
        parts = ["manual"]
    out_dir = settings.base_storage_path.joinpath(category, kind, *parts)
    name = slug(meta.get("title") or meta["video_id"])
    out_dir.mkdir(parents=True, exist_ok=True)
    last: Exception = DownloadFailed("aucun sélecteur")
    for i, sel in enumerate(_selectors(meta["format_id"])):
        try:
            with yt_dlp.YoutubeDL(_opts(sel, out_dir, 1 if i == 0 else 3, name)) as ydl:
                info = ydl.extract_info(meta["url"], download=True)
            path = Path(info["requested_downloads"][0]["filepath"])
            if path.exists():
                return path
            last = DownloadFailed(f"fichier absent: {path}")
        except yt_dlp.utils.DownloadError as e:
            last = DownloadFailed(str(e))
            log(f"{meta.get('video_id')} sélecteur échoué: {sel[:40]} -> {str(e)[:120]}")
    raise last
