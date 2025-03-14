# Build stage
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install build dependencies and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Final stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install curl for healthcheck and git for wiki mirroring
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Create logs and config directories
RUN mkdir -p logs
RUN mkdir -p /app/data/config

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GITMIRROR_CONFIG_DIR=/app/data/config

# Create a non-root user for security
RUN useradd -m appuser && \
    chown -R appuser:appuser /app && \
    chmod +x start.sh
USER appuser

# Expose port for web UI
EXPOSE 5000

# Note: Environment variables should be passed at runtime using --env-file
# Example: docker run --rm -p 5000:5000 --env-file .env github-gitea-mirror

# Set the entrypoint to our startup script
ENTRYPOINT ["/app/start.sh"]

# Default command (can be overridden)
CMD ["web"] 