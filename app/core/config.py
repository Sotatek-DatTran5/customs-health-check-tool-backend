from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # App
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "postgresql://user:password@postgres:5432/chc"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-southeast-1"
    AWS_ENDPOINT_URL: str = ""  # LocalStack: http://localhost:4566
    S3_BUCKET_NAME: str = "chc-files"

    # SMTP (MailHog in dev, real SMTP in prod)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@chc.com"

    # AWS SES (optional — leave empty to use SMTP above)
    SES_SENDER_EMAIL: str = ""

    # AI API
    AI_API_URL: str = ""
    AI_API_KEY: str = ""

    # Domain
    ADMIN_DOMAIN: str = "localhost"
    BASE_DOMAIN: str = "localhost"

    # Security
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    MAX_UPLOAD_SIZE_MB: int = 50


settings = Settings()
