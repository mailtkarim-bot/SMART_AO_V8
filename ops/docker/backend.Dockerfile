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
    && install --directory --owner=smartao --group=smartao --mode=0700 /var/lib/smart_ao/dce-quarantine \
    && install --directory --owner=smartao --group=smartao --mode=0700 /var/lib/smart_ao/models

COPY pyproject.toml README.md ./
COPY backend ./backend
ARG SMART_AO_INSTALL_RAG=0
ARG SMART_AO_INSTALL_DOCUMENT_ADVANCED=0
ARG SMART_AO_INSTALL_CONNECTORS=0
ARG SMART_AO_INSTALL_NOTIFICATIONS=0
RUN pip install --no-cache-dir . \
    && if [ "$SMART_AO_INSTALL_RAG" = "1" ]; then \
        pip install --no-cache-dir ".[rag]"; \
    fi \
    && if [ "$SMART_AO_INSTALL_DOCUMENT_ADVANCED" = "1" ]; then \
        pip install --no-cache-dir ".[document-advanced]"; \
    fi \
    && if [ "$SMART_AO_INSTALL_CONNECTORS" = "1" ]; then \
        pip install --no-cache-dir ".[connectors]"; \
    fi \
    && if [ "$SMART_AO_INSTALL_NOTIFICATIONS" = "1" ]; then \
        pip install --no-cache-dir ".[notifications]"; \
    fi \
    && chown -R smartao:smartao /app

USER smartao
EXPOSE 8000
CMD ["uvicorn", "app.bootstrap.production:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=172.30.0.0/24"]
