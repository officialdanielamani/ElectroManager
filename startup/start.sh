#!/bin/bash
set -e

echo "=========================================="
echo "  Inventory Manager - Startup"
echo "=========================================="
echo ""

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Run Python initialization
python3 "$SCRIPT_DIR/init.py"
if [ $? -ne 0 ]; then
    echo "Startup failed"
    exit 1
fi

echo ""
echo "Starting Flask application..."
echo "Access: http://localhost:5000"
echo ""

exec python3 app.py
