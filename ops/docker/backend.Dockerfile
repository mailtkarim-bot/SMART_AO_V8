FROM python:3.12-slim@sha256:876416ecde9aca2bcc90e1fb0c7a9500bbf749f5788b70f82d4c5a5c2357f8b4

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    SMART_AO_DCE_QUARANTINE_ROOT=/var/lib/smart_ao/dce-quarantine

RUN apt-get update \
    && apt-get upgrade --no-install-recommends --yes \
    && apt-get install --no-install-recommends --yes libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 smartao \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home smartao \
    && install --directory --owner=smartao --group=smartao --mode=0700 /var/lib/smart_ao/dce-quarantine

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir . \
    && chown -R smartao:smartao /app

USER smartao
EXPOSE 8000
CMD ["uvicorn", "app.bootstrap.production:app", "--host", "0.0.0.0", "--port", "8000"]
