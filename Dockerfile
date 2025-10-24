# Frfr Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    imagemagick \
    tesseract-ocr \
    tesseract-ocr-eng \
    git \
    build-essential \
    gcc \
    g++ \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# Copy application code
COPY frfr/ ./frfr/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# Create session storage directory
RUN mkdir -p .frfr_sessions

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMPORAL_ADDRESS=temporal:7233

# Expose any necessary ports (none needed for CLI)
# EXPOSE 8000

CMD ["bash"]
