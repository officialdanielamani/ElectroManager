#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Docker Startup"
echo "=========================================="
echo ""

# Create required directories
echo "[*] Creating directories..."
mkdir -p /app/instance
mkdir -p /app/uploads/locations
chmod 755 /app/instance /app/uploads /app/uploads/locations
echo "[OK] Directories ready"

# Initialize database
echo "[*] Initializing database..."
python init_db.py

# Start application
echo ""
echo "=========================================="
echo "  Starting Flask Application"
echo "=========================================="
echo ""
echo "Access at: http://YOUR_SERVER_IP:5000"
echo ""
echo "Default Login:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "!! CHANGE PASSWORD IMMEDIATELY !!"
echo ""
echo "=========================================="
echo ""

exec python app.py
