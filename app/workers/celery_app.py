from celery import Celery
from app.config import settings

celery_app = Celery(
    "pricepulse_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.scrape_tasks",
        "app.workers.alert_tasks",
        "app.workers.notification_tasks",
        "app.workers.polling_tasks",
        "app.workers.search_sync_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.scrape_tasks.*": {"queue": "scraping"},
        "app.workers.alert_tasks.*": {"queue": "alerts"},
        "app.workers.notification_tasks.*": {"queue": "notifications"},
        "app.workers.polling_tasks.*": {"queue": "default"},
        "app.workers.search_sync_tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "poll-due-products-every-minute": {
            "task": "app.workers.polling_tasks.schedule_due_scrapes",
            "schedule": 60.0,
        },
    },
)
