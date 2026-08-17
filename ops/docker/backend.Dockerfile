FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

RUN apt-get update \
    && apt-get install --no-install-recommends --yes libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "app.bootstrap.production:app", "--host", "0.0.0.0", "--port", "8000"]
