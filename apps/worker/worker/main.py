from __future__ import annotations
import os
import time
import redis
from rq import Worker, Queue, Connection

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
listen = ["default"]


def main() -> None:
    conn = redis.from_url(redis_url)
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        print("Worker started; waiting for jobs...")
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
