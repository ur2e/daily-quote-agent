from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "daily-quote-agent"
    aws_region: str = "ap-northeast-2"
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_endpoint_url: str | None = None
    bedrock_temperature: float = 1.0
    dynamodb_daily_quotes_table_name: str = "daily-quotes"
    dynamodb_users_table_name: str = "daily-quote-users"
    duplicate_check_limit: int = 20
    quote_generation_attempts: int = 20
    tavily_api_key: str | None = None
    quote_validation_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
