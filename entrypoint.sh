#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL at $DATABASE_HOST:$DATABASE_PORT..."
until nc -z "$DATABASE_HOST" "$DATABASE_PORT"; do
  sleep 1
done
echo "✅ PostgreSQL is up!"

echo "⏳ Waiting for Redis..."
until nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis is up!"

echo "⏳ Waiting for RabbitMQ..."
until nc -z rabbitmq 5672; do
  sleep 1
done
echo "✅ RabbitMQ is up!"

echo "📦 Running migrations..."
cd /app/xris
python manage.py migrate

echo "🧹 Clearing out old static files…"
# Remove everything under STATIC_ROOT
rm -rf /app/xris/static/*

echo "📁 Collecting static files…"
python manage.py collectstatic --noinput

echo "🚀 Starting service: $*"
exec "$@"
