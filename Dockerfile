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

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create instance directory for SQLite database
RUN mkdir -p instance

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Make startup script executable
RUN chmod +x startup.sh

# Run the application via startup script
CMD ["./startup.sh"]
