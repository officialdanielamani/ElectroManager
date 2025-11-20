#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Linux Setup"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Install Python 3.11 or higher"
    exit 1
fi

echo "[OK] Python found: $(python3 --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi
echo "[OK] Virtual environment ready"

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "[*] Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies
echo "[*] Installing dependencies..."
pip install -r requirements.txt
echo "[OK] Dependencies installed"

# Create .env from example
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[*] Creating .env file..."
        cp .env.example .env
    fi
fi

# Create required directories
echo "[*] Creating directories..."
mkdir -p uploads/locations
mkdir -p instance
chmod 755 uploads uploads/locations instance
echo "[OK] Directories created"

# Database initialization
if [ -f instance/inventory.db ]; then
    echo "[OK] Database exists"
else
    echo "[*] Initializing database..."
    python init_db.py
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Default Login:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "!! CHANGE PASSWORD IMMEDIATELY !!"
echo ""
echo "To start the application:"
echo "1. source venv/bin/activate"
echo "2. python app.py"
echo "3. Open browser: http://localhost:5000"
echo ""
