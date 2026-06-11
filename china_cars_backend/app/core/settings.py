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
    translation_proxy_url: str | None = None
    translation_proxy_token: str | None = None
    translation_proxy_timeout_ms: int = 15000

    # manager bot ingest
    manager_api_key: str | None = None

    # lead notifications from site modal
    lead_api_token: str | None = None
    lead_relay_url: str | None = None
    lead_relay_token: str | None = None
    lead_relay_timeout_ms: int = 15000
    telegram_bot_token: str | None = None
    telegram_group_id: str | None = None
    lead_rate_limit_per_minute: int = 20
    exchange_rate_api_url_template: str = "https://open.er-api.com/v6/latest/{base}"
    exchange_rate_api_timeout_ms: int = 4000

    # neutral external catalog importer
    external_market_base_url: str | None = None
    external_market_china_path: str = "/catalog"
    external_market_korea_path: str = "/korea"
    external_market_china_daily_limit: int = 3
    external_market_korea_daily_limit: int = 3
    external_market_max_pages: int = 20
    external_market_max_images: int = 10
    external_market_throttle_ms: int = 1000

    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def scraper_sources_list(self) -> list[str]:
        return [x.lower() for x in _split_csv(self.scraper_sources)]


settings = Settings()  # type: ignore[call-arg]
