#!/bin/bash
set -e

cd /app/xris

# Wait for database or redis if needed using netcat, e.g.:
# until nc -z redis 6379; do echo "Waiting for Redis..."; sleep 2; done

# Django setup
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
