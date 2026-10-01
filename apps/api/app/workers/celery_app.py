from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "roleradar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1)


@celery_app.task(name="roleradar.ping")
def ping() -> str:
    """Liveness task used to verify the worker/broker wiring."""
    return "pong"
