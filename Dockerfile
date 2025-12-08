# ============================================
# FILE: Dockerfile
# Copy this to your new project as Dockerfile
# ============================================

# Base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    fonts-dejavu \
    fonts-liberation \
    fonts-freefont-ttf \
    fontconfig \
    xvfb \
    xfonts-75dpi \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# Install Google Fonts (Poppins) - optional, skip if not available
RUN apt-get update && apt-get install -y fonts-googlefonts || true

# Install wkhtmltopdf with dependency handling
RUN apt-get update && \
    # Install modern SSL and JPEG libraries
    apt-get install -y libssl3 libjpeg62-turbo 2>/dev/null || \
    apt-get install -y libssl3 2>/dev/null || true && \
    # Create symlinks for compatibility with old .deb package
    (ln -sf /usr/lib/x86_64-linux-gnu/libssl.so.3 /usr/lib/x86_64-linux-gnu/libssl.so.1.1 2>/dev/null || true) && \
    (ln -sf /usr/lib/x86_64-linux-gnu/libjpeg.so.8 /usr/lib/x86_64-linux-gnu/libjpeg.so.62 2>/dev/null || true) && \
    # Download and install wkhtmltopdf
    wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb && \
    dpkg -i --force-depends wkhtmltox_0.12.6-1.buster_amd64.deb 2>&1 || true && \
    # Don't run apt-get install -f as it removes the package, just verify it exists
    (which wkhtmltopdf || echo "wkhtmltopdf not in PATH") && \
    rm -f wkhtmltox_0.12.6-1.buster_amd64.deb && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app code
COPY . .

# Clean up cache
RUN find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
RUN find . -name "*.pyc" -delete 2>/dev/null || true

# Expose port
EXPOSE 8000

# Run the app with gunicorn
CMD ["gunicorn", "app:app", "--bind=0.0.0.0:8000", "--workers=1", "--timeout=120"]