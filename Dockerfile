FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libpq-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

COPY . /app

RUN useradd -m appuser
USER appuser

CMD bash -lc 'gunicorn "prototipo_convenios_vacaciones_app:create_app()" \
    --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120'
