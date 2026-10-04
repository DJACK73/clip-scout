import shutil
from app.settings import settings

def free_disk_gb() -> float:
    return shutil.disk_usage(settings.base_storage_path).free / (1024 ** 3)
