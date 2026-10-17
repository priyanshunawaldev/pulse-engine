from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "pulseengine",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    "nightly-reconciliation": {
        "task": "app.workers.tasks.run_nightly_reconciliation",
        "schedule": crontab(hour="2", minute="0"),  # Runs daily at 02:00 UTC
    }
}
