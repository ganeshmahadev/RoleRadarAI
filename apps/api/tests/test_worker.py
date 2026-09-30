from app.workers.celery_app import celery_app, ping


def test_ping_task_registered() -> None:
    assert "roleradar.ping" in celery_app.tasks


def test_ping_task_runs() -> None:
    assert ping.apply().get() == "pong"
