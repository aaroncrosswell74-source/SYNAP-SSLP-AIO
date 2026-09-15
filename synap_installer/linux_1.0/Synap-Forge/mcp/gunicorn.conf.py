import multiprocessing
import os

bind = os.getenv("INTERCEPTOR_BIND", "0.0.0.0:11439")

workers = int(os.getenv(
    "GUNICORN_WORKERS",
    multiprocessing.cpu_count()
))

threads = int(os.getenv(
    "GUNICORN_THREADS",
    "4"
))

worker_class = "gthread"

timeout = int(os.getenv(
    "GUNICORN_TIMEOUT",
    "120"
))

keepalive = 5

accesslog = "-"
errorlog = "-"

loglevel = os.getenv(
    "LOG_LEVEL",
    "info"
)

preload_app = False
