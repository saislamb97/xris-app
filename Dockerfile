# Start from slim Python
FROM python:3.12-slim

# Avoid .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Install OS deps, including GDAL C library and headers
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    gcc \
    curl \
    netcat-openbsd \
    gdal-bin \
    libgdal-dev \
    pkg-config \
  && rm -rf /var/lib/apt/lists/*

# 2) Copy requirements and install Python deps,
#    but strip out GDAL from your original list and
#    then install the wheel that matches gdal-config's version.
COPY requirements.txt .
RUN grep -v '^GDAL==' requirements.txt > req_no_gdal.txt \
 && pip install --upgrade pip \
 && pip install flower \
 && pip install -r req_no_gdal.txt \
 && pip install "GDAL==$(gdal-config --version)"

# 3) Copy all your app code in one go
COPY . .

# 4) Prepare Celery-beat schedule dir
RUN mkdir -p /app/celerydata

# 5) Entrypoint for waiting/migrations/etc.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
# Default to running Daphne; overridden in docker-compose for Celery/Beat/Flower
CMD ["daphne", "-e", "tcp:8000:interface=0.0.0.0", "xris.asgi:application"]
