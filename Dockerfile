FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for QR, barcode, and PDF generation
RUN apt-get update && apt-get install -y \
    sqlite3 \
    libpango-1.0-0 \
    libpango1.0-dev \
    libpangoft2-1.0-0 \
    libffi-dev \
    libcairo2 \
    libcairo2-dev \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (separate layer for better caching)
COPY requirements.txt .

# Install Python dependencies (cached unless requirements.txt changes)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure runtime directories exist (static asset dirs are already in repo)
RUN mkdir -p instance static/custom/font static/custom/theme

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Make startup scripts executable
RUN chmod +x startup/start.sh startup/docker.sh

# Run the application via startup script
CMD ["./startup/docker.sh"]
