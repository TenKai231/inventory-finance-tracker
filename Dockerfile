# Multi-stage build — Python 3.12 + Debian Bookworm (stable)
FROM python:3.12-slim as builder

WORKDIR /app

# # ✅ Install build dependencies yang ADA di Bookworm
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     gcc \
#     g++ \
#     gfortran \
#     libblas-dev \
#     liblapack-dev \
#     && rm -rf /var/lib/apt/lists/*

RUN echo "deb http://kambing.ui.ac.id/debian trixie main contrib non-free" > /etc/apt/sources.list && \
  echo "deb http://kambing.ui.ac.id/debian trixie-updates main contrib non-free" >> /etc/apt/sources.list && \
  echo "deb http://kambing.ui.ac.id/debian-security trixie-security main contrib non-free" >> /etc/apt/sources.list && \
  apt-get update && apt-get install -y --no-install-recommends \
  build-essential gcc g++ gfortran libblas-dev liblapack-dev \
  && rm -rf /var/lib/apt/lists/*

# Setup virtualenv
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dengan preferensi binary wheel (hindari compile jika ada)
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir --prefer-binary -r requirements.txt

# Stage 2: Production image (kecil)
FROM python:3.12-slim

WORKDIR /app

# Copy virtualenv dari builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy app code (exclude artifacts)
COPY . .
RUN rm -rf /app/.venv /app/__pycache__ /app/.pytest_cache /app/*.log 2>/dev/null || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# Dynamic port untuk Render/Railway
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 2 --timeout 60 run:app"]
