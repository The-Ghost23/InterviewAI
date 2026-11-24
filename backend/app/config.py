from pathlib import Path
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    speech_model_dir: str = str(Path(__file__).resolve().parents[1] / ".models" / "whisper-base.en")


    @field_validator('database_url', mode='before')
    @classmethod
    def empty_database_url(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


settings = Settings()
