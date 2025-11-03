FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Chromium (works on both amd64 and arm64)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    git \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Clone GoogleFindMyTools repository
RUN git clone https://github.com/leonboe1/GoogleFindMyTools.git /app/GoogleFindMyTools

# Copy patch scripts and apply them
COPY patch_chrome_driver.py /app/
COPY patch_fcm_receiver.py /app/
RUN python3 /app/patch_chrome_driver.py && \
    python3 /app/patch_fcm_receiver.py

# Copy auth_data directory if it exists (optional - for standalone deployment without volume mounts)
# This will be overridden by volume mount if specified in docker-compose.yml
# The .dockerignore file should NOT exclude auth_data if you want to include it
COPY --chown=root:root auth_data /app/auth_data

# Create symlink to support both deployment methods:
# 1. Standalone: Uses the copied secrets.json from /app/auth_data/
# 2. With volume mount to /app/auth_data: Symlink points to mounted directory
# 3. With direct file mount to /app/GoogleFindMyTools/Auth/secrets.json: Symlink is overridden
RUN ln -sf /app/auth_data/secrets.json /app/GoogleFindMyTools/Auth/secrets.json

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/app/

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/GoogleFindMyTools
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Device service configuration (can be overridden in docker-compose.yml)
ENV DEVICE_CACHE_TTL=60
ENV LOCATION_UPDATE_INTERVAL=300
ENV ENABLE_LOCATION_UPDATES=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

