from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "app/.env"), extra="ignore")

    database_url: str
    api_host: str = "127.0.0.1"
    api_port: int = 8010
    cors_origins: str = ""
    media_dir: str = "./data/media"

    # ingestion defaults
    initial_load_limit: int = 30
    daily_new_limit: int = 75
    daily_delete_limit: int = 0
    che168_max_images: int = 10
    scraper_sources: str = "che168,dongchedi,guazi"
    scraper_throttle_ms: int = 700
    scraper_skip_existing: bool = True

    # translation
    openai_api_key: str | None = None
    openai_translation_model: str = "gpt-5-nano"
    openai_normalize_model: str = "gpt-5-nano"

    # manager bot ingest
    manager_api_key: str | None = None

    # lead notifications from site modal
    lead_api_token: str | None = None
    telegram_bot_token: str | None = None
    telegram_group_id: str | None = None
    lead_rate_limit_per_minute: int = 20

    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def scraper_sources_list(self) -> list[str]:
        return [x.lower() for x in _split_csv(self.scraper_sources)]


settings = Settings()  # type: ignore[call-arg]
