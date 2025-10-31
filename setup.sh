#!/bin/bash

echo "=========================================="
echo "Inventory Manager - Setup Script"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env
    cat .env.example | grep -v SECRET_KEY >> .env
fi

# Create uploads directory
echo "Creating uploads directory..."
mkdir -p uploads

# Initialize database
echo "Initializing database..."
flask --app app init-db

# Create admin user
echo ""
echo "=========================================="
echo "Create Admin User"
echo "=========================================="
flask --app app create-admin

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To start the application:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Run the app: python app.py"
echo "3. Open browser: http://localhost:5000"
echo ""
