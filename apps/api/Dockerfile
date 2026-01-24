# Multi-stage build for Azure Container Apps
# Build context: repo root (not apps/api)
# Installs marker-pdf + torch during build (avoids Kudu timeout)

FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first to avoid 5GB+ CUDA packages (saves disk space)
RUN pip install --user --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy and install shared package FIRST (evidence_shared)
COPY packages/shared/python /build/shared
RUN pip install --user --no-cache-dir /build/shared

# Then install the rest of the requirements
COPY apps/api/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies for marker-pdf (OpenCV, etc)
# Note: libgl1 replaces libgl1-mesa-glx in Debian Trixie (python:3.12-slim base)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security (wsskeptic fix)
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder to user directory
COPY --from=builder /root/.local /home/appuser/.local
RUN chown -R appuser:appuser /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code (from apps/api/ in repo root context)
COPY --chown=appuser:appuser apps/api/ .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
