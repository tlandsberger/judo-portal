#!/bin/sh
# Start des Containers: Datenbank migrieren, ggf. ersten Administrator einladen, dann Gunicorn.
set -e
python manage.py migrate --noinput
python manage.py bootstrap_admin
exec gunicorn portal.wsgi:application --config gunicorn.conf.py
