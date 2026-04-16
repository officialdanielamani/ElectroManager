#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Docker Startup"
echo "=========================================="
echo ""

# Run initialization
python3 startup/init.py
if [ $? -ne 0 ]; then
    echo "Startup failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "Starting Flask application"
echo "=========================================="
echo ""
echo "Access: http://YOUR_SERVER_IP:5000"
echo "Default: admin / admin123"
echo ""

exec python3 app.py
