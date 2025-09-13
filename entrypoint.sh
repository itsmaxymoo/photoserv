#!/bin/sh
set -e

# Wait for database (optional if using wait-for-it.sh or pg_isready)
python manage.py migrate --noinput

# Start gunicorn
exec gunicorn --bind 0.0.0.0:8008 --workers 3 photoserv.wsgi:application
