#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Linux Setup"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    exit 1
fi

echo "[OK] Python found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv > /dev/null 2>&1
fi
echo "[OK] Virtual environment ready"

# Activate virtual environment
source venv/bin/activate

# Upgrade pip silently
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies
echo "[*] Installing Python dependencies..."
pip install -r requirements.txt --quiet
echo "[OK] Python dependencies installed"

# Download JavaScript libraries
echo "[*] Downloading JavaScript libraries..."
python init_libraries.py > /dev/null 2>&1 || echo "[WARNING] JavaScript library download failed - Internet may be required"
echo "[OK] JavaScript libraries ready"

# Create .env from example
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env > /dev/null 2>&1
    fi
fi

# Create required directories
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
    echo "[OK] Database initialized"
fi

echo ""
echo "=========================================="
echo "  Setup Complete"
echo "=========================================="
echo ""
echo "Default Login:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "WARNING: Change password immediately!"
echo ""
echo "To start the application:"
echo "  python app.py"
echo "  Open: http://localhost:5000"
echo ""
