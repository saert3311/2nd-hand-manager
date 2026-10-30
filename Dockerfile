# ==============================================================================
# Production Dockerfile for 2ndHand Staging Hub
# Python 3.13 Slim • Non-Root Security • Gunicorn WSGI • WhiteNoise Static
# ==============================================================================

FROM python:3.13-slim-bookworm

# Set Python operational environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Install runtime OS dependencies and curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group (UID/GID 10001)
RUN groupadd -r -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Create necessary persistent and static storage directories
RUN mkdir -p /app/data /app/media /app/staticfiles && \
    chown -R appuser:appgroup /app

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt /app/

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Build metadata arguments
ARG BUILD_TIME=""
ARG BUILD_COMMIT=""
ARG APP_VERSION="2.6.0"

ENV APP_BUILD_TIME=${BUILD_TIME} \
    APP_BUILD_COMMIT=${BUILD_COMMIT} \
    APP_VERSION=${APP_VERSION}

# Copy application source code with non-root ownership
COPY --chown=appuser:appgroup . /app/

# Bake build date/time and commit files into container image
RUN if [ -z "$BUILD_TIME" ]; then \
        date -u +"%Y-%m-%d %H:%M UTC" > /app/build_date.txt; \
    else \
        echo "$BUILD_TIME" > /app/build_date.txt; \
    fi && \
    if [ -n "$BUILD_COMMIT" ]; then \
        echo "$BUILD_COMMIT" > /app/build_commit.txt; \
    fi && \
    chown appuser:appgroup /app/build_date.txt /app/build_commit.txt 2>/dev/null || true

# Ensure entrypoint script has execution permissions
RUN chmod +x /app/docker/entrypoint.sh

# Switch to unprivileged non-root user
USER appuser

# Expose internal application port
EXPOSE 8000

# Container healthcheck testing root endpoint responsiveness
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/ || exit 1

# Define container entrypoint and default Gunicorn command
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
