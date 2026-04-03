from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "postgresql://user:password@postgres:5432/chc"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"

    # AWS (optional — if not set, S3/email will log to console in dev mode)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-southeast-1"
    S3_BUCKET_NAME: str = ""
    SES_SENDER_EMAIL: str = ""

    # AI API
    AI_API_URL: str = ""
    AI_API_KEY: str = ""

    # Domain
    ADMIN_DOMAIN: str = "localhost"
    BASE_DOMAIN: str = "localhost"

    class Config:
        env_file = ".env"


settings = Settings()
