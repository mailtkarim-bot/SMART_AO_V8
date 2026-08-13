FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "app.bootstrap.application:app", "--host", "0.0.0.0", "--port", "8000"]
