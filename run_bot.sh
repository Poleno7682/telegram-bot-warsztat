#!/bin/bash
# Telegram Bot Launcher for Linux/Mac
# This script runs the bot with proper environment

echo "========================================"
echo "   Telegram Bot - Auto Service"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -f "backend/venv/bin/activate" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo "Please run setup_linux.sh first"
    exit 1
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
source backend/venv/bin/activate

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "[ERROR] Configuration file .env not found!"
    echo "Please copy backend/env.example to backend/.env and configure it"
    exit 1
fi

# Run the bot
echo "[INFO] Starting bot..."
echo ""
python3 run_bot.py

# Deactivate on exit
deactivate

