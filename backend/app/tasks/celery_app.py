import os
from celery import Celery

celery = Celery(
    "thandev",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

@celery.task
def ingest_nvd():
    # TODO: implement
    return "ok"

@celery.task
def ingest_kev():
    # TODO: implement
    return "ok"

@celery.task
def enrich_pending():
    # TODO: implement
    return "ok"
