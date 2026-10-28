from functools import lru_cache
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: SecretStr
    redis_url: SecretStr = SecretStr('redis://localhost:6379/0')
    cache_ttl: int = Field(default=60, ge=1)
    admin_api_key: SecretStr = Field(min_length=16)
    internal_api_key: SecretStr = Field(min_length=16)

    @model_validator(mode='after')
    def distinct_keys(self):
        if self.admin_api_key.get_secret_value() == self.internal_api_key.get_secret_value():
            raise ValueError('Admin and internal API keys must differ')
        return self

@lru_cache
def get_settings():
    return Settings()
