from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str
    CELERY_BROKER_URL: str

    # AWS
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str
    SES_SENDER_EMAIL: str

    # AI API
    AI_API_URL: str
    AI_API_KEY: str = ""

    # Domain
    ADMIN_DOMAIN: str
    BASE_DOMAIN: str

    class Config:
        env_file = ".env"


settings = Settings()
