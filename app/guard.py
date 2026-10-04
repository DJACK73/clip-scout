import random
import shutil
import time
from pathlib import Path
from app.settings import settings
from app.paths import free_disk_gb
from app.exceptions import DiskQuotaExceeded
from app.logger import log

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

COOKIES_PATH = Path(__file__).resolve().parent.parent / "config" / "cookies.txt"
DENO_PATH = shutil.which("deno") or str(Path.home() / ".deno" / "bin" / "deno")

def check_disk() -> None:
    free = free_disk_gb()
    if Path("/mnt/c").exists():
        free = min(free, shutil.disk_usage("/mnt/c").free / 1e9)
    if free < settings.min_free_disk_gb:
        raise DiskQuotaExceeded(f"{free:.1f} Go libres < {settings.min_free_disk_gb} Go")

def network_delay() -> None:
    delay = random.uniform(3, 15)
    log(f"Délai réseau {delay:.1f}s")
    time.sleep(delay)

def build_ydl_opts() -> dict:
    opts: dict = {
        "http_headers": {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": random.choice(["en-US,en;q=0.9", "fr-FR,fr;q=0.9,en;q=0.8"]),
        },
        "quiet": True,
        "no_warnings": True,
        "sleep_interval": 3,
        "max_sleep_interval": 8,
        "sleep_interval_requests": 1,
        "js_runtimes": {"deno": {"path": DENO_PATH}},
    }
    if COOKIES_PATH.exists() and COOKIES_PATH.stat().st_size > 0:
        opts["cookiefile"] = str(COOKIES_PATH)
    return opts
