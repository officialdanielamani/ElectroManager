#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Linux Setup"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 is not installed"
    exit 1
fi

echo "[OK] Python found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi
echo "[OK] Virtual environment ready"

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip -q

# Install dependencies
echo "[*] Installing Python dependencies..."
pip install -r requirements.txt -q
echo "[OK] Dependencies installed"

# Initialize
echo "[*] Running startup..."
python3 startup/init.py
if [ $? -ne 0 ]; then
    echo "[!] Startup failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "  Setup Complete"
echo "=========================================="
echo "Default Login:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "To start: python3 app.py"
echo "Access: http://localhost:5000"
echo ""
