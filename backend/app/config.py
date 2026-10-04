from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    serpapi_api_key: str = ""
    trippilot_fixtures: bool = False

    llm_provider: str = "openai"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    redis_url: str = ""
    database_url: str = ""

    trippilot_host: str = "0.0.0.0"
    trippilot_port: int = 8000
    trippilot_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    trippilot_search_budget: int = 40

    @property
    def fixture_mode(self) -> bool:
        return self.trippilot_fixtures or not self.serpapi_api_key

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.trippilot_cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
