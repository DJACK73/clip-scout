import json
import subprocess
from pathlib import Path
from typing import Any
from app.settings import settings
from app.exceptions import QualityRejected

def probe(path: Path) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise QualityRejected(f"ffprobe: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)

def _fps(rate: str) -> float:
    n, _, d = rate.partition("/")
    return float(n) / float(d or 1) if float(d or 1) else 0.0

def check(path: Path, min_fps: float | None = None, min_kbps: int | None = None) -> dict[str, Any]:
    data = probe(path)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        raise QualityRejected("pas de flux vidéo")
    if not a:
        raise QualityRejected("pas de flux audio")
    fps = _fps(v.get("avg_frame_rate", "0/1"))
    kbps = int(data["format"].get("bit_rate", 0)) // 1000
    if fps < (min_fps if min_fps is not None else settings.min_video_fps) - 1:
        raise QualityRejected(f"fps {fps:.1f}")
    if kbps < (min_kbps if min_kbps is not None else settings.min_video_bitrate):
        raise QualityRejected(f"bitrate {kbps}kbps")
    return {"fps": round(fps, 1), "kbps": kbps, "height": v["height"], "codec": v["codec_name"], "size_mb": path.stat().st_size // 1_000_000}
