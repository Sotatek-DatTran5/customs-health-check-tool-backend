from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "chc",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=["app.requests.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "sla-compliance-check": {
            "task": "app.requests.tasks.check_sla_compliance",
            "schedule": crontab(minute=0),  # Every hour
        },
    },
)
