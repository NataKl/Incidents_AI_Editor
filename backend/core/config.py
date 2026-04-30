from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "admin_editor"
    postgres_password: str = ""
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "ai_editor"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.2

    # Запросы к OpenAI (обход geo-restrictions); читается из HTTPS_PROXY / HTTP_PROXY
    https_proxy: str = ""
    http_proxy: str = ""

    @property
    def db_conninfo(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
