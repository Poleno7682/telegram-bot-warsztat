#!/bin/bash
# Linux/Mac Setup Script for Telegram Bot (Docker)
# Prepares .env and builds the Docker image. See docs/DOCKER.md for details.

set -e

echo "========================================"
echo "   Telegram Bot - Setup (Docker)"
echo "========================================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed"
    echo "Install it from: https://docs.docker.com/engine/install/"
    exit 1
fi

echo "[INFO] Docker found"
docker --version
echo ""

# Check Docker Compose (v2 plugin, "docker compose", not the old "docker-compose")
if ! docker compose version &> /dev/null; then
    echo "[ERROR] Docker Compose plugin is not available (tried: docker compose version)"
    echo "Install it from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "[INFO] Docker Compose found"
docker compose version
echo ""

# Create .env if not exists
if [ ! -f "backend/.env" ]; then
    echo "[INFO] Creating .env file..."
    cp backend/env.example backend/.env
    echo "[SUCCESS] .env file created"
    echo "[IMPORTANT] Please edit backend/.env and add your BOT_TOKEN and ADMIN_IDS"
else
    echo "[INFO] backend/.env already exists"
fi

# Build the image (migrations run automatically on container start, not here)
echo ""
echo "[INFO] Building Docker image..."
docker compose build

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
echo "For a local PostgreSQL instead of an external database, see docs/DOCKER.md"
echo ""
