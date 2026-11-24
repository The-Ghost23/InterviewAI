from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import model_validator
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal['development', 'production'] = 'development'
    ai_provider: Literal['ollama', 'runpod'] = 'ollama'
    runpod_base_url: str = ''
    runpod_api_key: SecretStr | None = None
    runpod_model: str = 'Qwen/Qwen3-4B'
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    database_url: SecretStr | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    speech_model_dir: str = str(Path(__file__).resolve().parents[1] / ".models" / "whisper-base.en")


    @field_validator('database_url', 'runpod_api_key', mode='before')
    @classmethod
    def empty_database_url(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def active_model(self) -> str:
        return self.runpod_model if self.ai_provider == 'runpod' else self.ollama_model

    @model_validator(mode='after')
    def deployment_configuration(self):
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError('CORS_ORIGINS must contain exact origins without paths or wildcards.')
        if self.runpod_base_url:
            parsed = urlsplit(self.runpod_base_url)
            if parsed.scheme != 'https' or parsed.hostname != 'api.runpod.ai' or parsed.username or parsed.query or parsed.fragment or not parsed.path.rstrip('/').endswith('/openai/v1'):
                raise ValueError('RUNPOD_BASE_URL must be the HTTPS Runpod OpenAI-compatible endpoint URL.')
        if self.app_env == 'production':
            if not self.database_url or not self.supabase_url.startswith('https://') or not self.supabase_publishable_key:
                raise ValueError('Production requires database and Supabase authentication configuration.')
            if self.ai_provider != 'runpod' or not self.runpod_base_url or not self.runpod_api_key:
                raise ValueError('Production requires a configured Runpod provider.')
            if not self.cors_origins or any(not origin.startswith('https://') for origin in self.cors_origins):
                raise ValueError('Production requires explicit HTTPS frontend origins.')
        return self


settings = Settings()
