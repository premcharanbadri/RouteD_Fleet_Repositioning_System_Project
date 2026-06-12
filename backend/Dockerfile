FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir ".[postgres]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
