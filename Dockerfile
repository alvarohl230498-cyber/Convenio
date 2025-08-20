FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# Librerías del sistema necesarias para WeasyPrint + Postgres
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

# Dependencias Python
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Código
COPY . /app

# Usuario no-root
RUN useradd -m appuser
USER appuser

EXPOSE 8080

# Gunicorn en forma JSON (mejor manejo de señales)
CMD ["gunicorn", "prototipo_convenios_vacaciones_app:create_app()", \
    "--bind", "0.0.0.0:${PORT}", "--workers", "2", "--threads", "4", "--timeout", "120"]