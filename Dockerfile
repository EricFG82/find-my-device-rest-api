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

# Create auth_data directory (will be populated by volume mount)
RUN mkdir -p /app/auth_data

# Create symlink to support volume mount deployment
# The secrets.json will be mounted at /app/GoogleFindMyTools/Auth/secrets.json via docker-compose.yml
RUN mkdir -p /app/GoogleFindMyTools/Auth

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

