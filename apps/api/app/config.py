from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "craft_cost API"
    app_env: str = "development"

    postgres_url: str = "postgresql+psycopg://postgres:postgres@db:5432/app"
    redis_url: str = "redis://redis:6379/0"

    storage_endpoint: str | None = None
    storage_bucket: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None

    session_secret: str = "dev_session_secret"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = ""

settings = Settings()
