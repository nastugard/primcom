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

    initial_load_limit: int = 30
    daily_new_limit: int = 5
    daily_delete_limit: int = 5

    che168_max_images: int = 16

    openai_api_key: str | None = None
    openai_translation_model: str = "gpt-5-nano"
    openai_normalize_model: str = "gpt-5-nano"

    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.cors_origins)


settings = Settings()  # type: ignore[call-arg]
