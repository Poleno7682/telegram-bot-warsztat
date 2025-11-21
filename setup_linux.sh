#!/bin/bash
# Linux/Mac Setup Script for Telegram Bot
# This script sets up the development environment

set -e

echo "========================================"
echo "   Telegram Bot - Setup (Linux/Mac)"
echo "========================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3.11 or higher"
    exit 1
fi

echo "[INFO] Python found"
python3 --version
echo ""

# Create virtual environment
if [ ! -d "backend/venv" ]; then
    echo "[INFO] Creating virtual environment..."
    cd backend
    python3 -m venv venv
    cd ..
    echo "[SUCCESS] Virtual environment created"
else
    echo "[INFO] Virtual environment already exists"
fi

echo ""
echo "[INFO] Activating virtual environment..."
source backend/venv/bin/activate

# Upgrade pip
echo "[INFO] Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "[INFO] Installing requirements..."
pip install -r backend/requirements.txt

# Create .env if not exists
if [ ! -f "backend/.env" ]; then
    echo "[INFO] Creating .env file..."
    cp backend/env.example backend/.env
    echo "[SUCCESS] .env file created"
    echo "[IMPORTANT] Please edit backend/.env and add your BOT_TOKEN and ADMIN_IDS"
else
    echo "[INFO] .env file already exists"
fi

# Create db directory
if [ ! -d "backend/db" ]; then
    echo "[INFO] Creating database directory..."
    mkdir -p backend/db
fi

# Run migrations
echo "[INFO] Running database migrations..."
cd backend
alembic upgrade head
cd ..

echo ""
echo "========================================"
echo "   Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit backend/.env with your BOT_TOKEN and ADMIN_IDS"
echo "2. Make run_bot.sh executable: chmod +x run_bot.sh"
echo "3. Run the bot with: ./run_bot.sh"
echo ""

deactivate

