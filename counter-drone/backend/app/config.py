from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Database -------------------------------------------------------
    database_url: str = "postgresql+asyncpg://postgres:Flash123@localhost:5432/counterdrones"
    
    # ---- Simulated sensor site -----------------------------------------

    sensor_name: str = "SENTINEL-1"
    sensor_lat: float = 37.7749
    sensor_lon: float = -122.4194

    # Everything beyond this range falls off the display.
    detection_range_m: float = 3000.0
    # A drone inside this ring raises an alert event.
    alert_radius_m: float = 900.0

    # ---- Simulator behaviour -------------------------------------------
    tick_seconds: float = 2.0          # how often new detections are produced
    min_active_objects: int = 3
    max_active_objects: int = 9
    spawn_chance: float = 0.35         # chance per tick of adding an object
    history_length: int = 40           # how many past positions we keep per track
    track_timeout_seconds: float = 12.0  # no updates for this long -> track lost

    # ---- Machine learning ----------------------------------------------
    # "sklearn" -> random forest on six summary features (default, fast)
    # "torch"   -> GRU over the raw report sequence (needs requirements-torch.txt)
    classifier_backend: str = "sklearn"
    model_path: str = "models/classifier.joblib"
    torch_model_path: str = "models/classifier_gru.pt"
    min_points_for_classification: int = 4

    # ---- API ------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
