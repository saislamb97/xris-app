#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
until nc -z "$DATABASE_HOST" "$DATABASE_PORT"; do
  sleep 1
done
echo "✅ PostgreSQL is up!"

# Wait for Redis
echo "⏳ Waiting for Redis..."
until nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis is up!"

# Wait for RabbitMQ
echo "⏳ Waiting for RabbitMQ..."
until nc -z rabbitmq 5672; do
  sleep 1
done
echo "✅ RabbitMQ is up!"

# Run database migrations
echo "📦 Running migrations..."
cd /app/xris
python manage.py migrate

# Optional: collect static files
# echo "📁 Collecting static files..."
# python manage.py collectstatic --noinput

# Run the command specified in Dockerfile/CMD or docker-compose
echo "🚀 Starting service..."
exec "$@"
