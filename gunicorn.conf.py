# Gunicorn: ein Worker mit Threads (SQLite, kleiner Verein), dazu der Zeitplaner für nächtliche Aufgaben.
bind = "0.0.0.0:8000"
workers = 1
threads = 8
worker_class = "gthread"
timeout = 60
accesslog = "-"
forwarded_allow_ips = "*"


def post_worker_init(worker):
    from portal.core import scheduler

    scheduler.start()
