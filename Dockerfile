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
    && rm -rf /var/lib/apt/lists/*

# Install Google Fonts (Poppins)
RUN apt-get update && apt-get install -y fonts-googlefonts || true

# Install wkhtmltopdf
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb && \
    dpkg -i wkhtmltox_0.12.6-1.buster_amd64.deb || apt-get install -f -y && \
    rm wkhtmltox_0.12.6-1.buster_amd64.deb

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

