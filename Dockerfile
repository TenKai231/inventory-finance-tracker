# Dockerfile — Production Ready for Render/Railway
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

# Install system dependencies (if needed for pandas/openpyxl)
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (cache layer)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app code
COPY . .

# Expose port (documentasi saja, Render pakai $PORT)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3   CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# Run with Gunicorn — dynamic port from env var $PORT
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 2 --timeout 60 run:app"]
