from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    async_database_url: str = (
        "postgresql+asyncpg://saleor:saleor@localhost:5432/saleor"
    )


settings = Settings()
