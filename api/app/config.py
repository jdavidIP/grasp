from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    openai_api_key: str = ""
    max_video_duration_seconds: int = 14400
    segmentation_breakpoint_percentile: float = 90.0
    min_segment_duration_seconds: int = 60
    # Segments must also be at least this fraction of the video (162s for 3 hours).
    min_segment_duration_fraction: float = 0.015
    max_segments_per_video: int = 40


settings = Settings()
