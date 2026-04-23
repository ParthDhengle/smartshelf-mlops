# SmartShelf API — Production Docker Image
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ src/
COPY pyproject.toml .
RUN pip install -e .

# Environment defaults
ENV PYTHONPATH=src
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "smartshelf.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
