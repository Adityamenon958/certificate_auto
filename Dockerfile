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

# Install OpenSSL 1.1 libraries (required by wkhtmltopdf)
# Download and install libssl1.1 from Debian Buster security updates
RUN apt-get update && \
    wget -q https://snapshot.debian.org/archive/debian-security/20221211T213352Z/pool/updates/main/o/openssl/libssl1.1_1.1.1n-0+deb10u4_amd64.deb -O /tmp/libssl1.1.deb || \
    wget -q http://ftp.debian.org/debian/pool/main/o/openssl/libssl1.1_1.1.1n-0+deb11u5_amd64.deb -O /tmp/libssl1.1.deb || \
    wget -q http://security.debian.org/debian-security/pool/updates/main/o/openssl/libssl1.1_1.1.1n-0+deb10u5_amd64.deb -O /tmp/libssl1.1.deb && \
    dpkg -i /tmp/libssl1.1.deb 2>&1 || apt-get install -f -y && \
    rm -f /tmp/libssl1.1.deb && \
    rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf with dependency handling
RUN apt-get update && \
    # Install JPEG library
    apt-get install -y libjpeg62-turbo 2>/dev/null || true && \
    # Create symlink for JPEG if needed
    (ln -sf /usr/lib/x86_64-linux-gnu/libjpeg.so.8 /usr/lib/x86_64-linux-gnu/libjpeg.so.62 2>/dev/null || true) && \
    # Download and install wkhtmltopdf
    wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb && \
    dpkg -i --force-depends wkhtmltox_0.12.6-1.buster_amd64.deb 2>&1 || true && \
    # Verify installation
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
