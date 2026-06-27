# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

WORKDIR /build

# Install compilation tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy and install python dependencies
COPY requirements.txt .
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -r requirements.txt


# Stage 2: Runtime image
FROM python:3.12-slim AS runner

WORKDIR /workspace

# Install system dependencies for processing (LibreOffice, Poppler, ClamAV client libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Configure virtual environment path
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/workspace"

# Copy backend source code
COPY . /workspace/backend

EXPOSE 8001

# Command is overridden in docker-compose/K8s for worker vs api
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
