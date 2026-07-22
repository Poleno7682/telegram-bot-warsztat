#!/bin/bash
# Telegram Bot Launcher for Linux/Mac (Docker)
# Builds (if needed) and runs the bot via docker compose, attached to logs.
# Press Ctrl+C to stop.

echo "========================================"
echo "   Telegram Bot - Auto Service"
echo "========================================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
    echo "[ERROR] Docker / Docker Compose not found!"
    echo "Please run setup_linux.sh first"
    exit 1
fi

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "[ERROR] Configuration file backend/.env not found!"
    echo "Please copy backend/env.example to backend/.env and configure it"
    exit 1
fi

# Run the bot (foreground; Ctrl+C stops the containers)
echo "[INFO] Starting bot..."
echo ""
docker compose up --build
