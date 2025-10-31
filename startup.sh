#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Docker Startup"
echo "=========================================="
echo ""

# Ensure required directories exist
echo "→ Ensuring required directories exist..."
mkdir -p /app/instance
mkdir -p /app/uploads
mkdir -p /app/uploads/locations
chmod 755 /app/instance
chmod 755 /app/uploads
chmod 755 /app/uploads/locations
echo "  ✓ Directories ready"

# Initialize database
echo ""
echo "→ Initializing database..."
python init_db.py

# Start application
echo ""
echo "=========================================="
echo "  Starting Flask application..."
echo "=========================================="
echo ""
echo "  Access at: http://YOUR_SERVER_IP:5000"
echo ""
echo "  Default credentials:"
echo "    Username: admin"
echo "    Password: admin123"
echo ""
echo "  ⚠️  CHANGE PASSWORD IMMEDIATELY!"
echo ""
echo "=========================================="
echo ""

exec python app.py
