#!/bin/bash
# Telegram Bot Launcher for Linux/Mac
# This script runs the bot with proper environment

echo "========================================"
echo "   Telegram Bot - Auto Service"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "[ERROR] Configuration file .env not found!"
    echo "Please copy backend/env.example to backend/.env and configure it"
    exit 1
fi

# Check if Python dependencies are installed
if ! python3 -c "import aiogram" 2>/dev/null; then
    echo "[ERROR] Python dependencies not installed!"
    echo "Please run setup_linux.sh first"
    exit 1
fi

# Run the bot
echo "[INFO] Starting bot..."
echo ""
python3 run_bot.py

