from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_base_url: str | None = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_model: str = "qwen-plus"

    amap_api_key: str

    mcp_server_command: str = "python"
    mcp_server_args: list[str] = ["-m", "app.mcp_server"]
    llm_timeout_sec: int = 60
    tool_timeout_sec: int = 20
    llm_max_retries: int = 2
    tool_max_retries: int = 1
    retry_backoff_sec: float = 1.5
    plan_timeout_sec: int = 120


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
