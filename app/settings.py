from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / "config" / ".env"), extra="ignore")

    gemini_keys: str
    gemini_model: str
    base_storage_path: Path
    database_path: Path
    min_free_disk_gb: int
    max_download_concurrency: int
    min_video_fps: int
    min_video_bitrate: int
    time_clip_buffer_sec: int
    search_backend: Literal["ytdlp", "gemini"] = "ytdlp"
    max_video_duration_sec: int = 1800
    min_video_duration_sec: int = 5
    min_video_height: int = 720
    max_video_height: int = 1080
    max_edit_per_job: int = 2

    @property
    def gemini_keys_list(self) -> list[str]:
        return [k.strip() for k in self.gemini_keys.split(",") if k.strip()]

settings = Settings()
