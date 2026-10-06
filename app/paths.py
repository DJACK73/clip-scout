import shutil
from pathlib import Path
from app.settings import settings

WINDOWS_DRIVE = Path("/mnt/c")

def free_disk_gb() -> float:
    free = shutil.disk_usage(settings.base_storage_path).free
    if WINDOWS_DRIVE.is_dir():
        free = min(free, shutil.disk_usage(WINDOWS_DRIVE).free)
    return free / (1024 ** 3)
