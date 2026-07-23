from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    async_database_url: str = (
        "postgresql+asyncpg://saleor:saleor@localhost:5432/saleor"
    )
    django_events_url: str = "http://localhost:8000/order-service/events/"
    order_service_shared_secret: str = "dev-secret-change-me"


settings = Settings()
