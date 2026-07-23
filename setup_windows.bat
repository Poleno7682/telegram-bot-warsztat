@echo off
REM Windows Setup Script for Telegram Bot (Docker)
REM Prepares .env and builds the Docker image. See docs/DOCKER.md for details.

echo ========================================
echo    Telegram Bot - Setup (Docker)
echo ========================================
echo.

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Install Docker Desktop from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo [INFO] Docker found
docker --version
echo.

REM Check Docker Compose (v2 plugin, "docker compose")
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose plugin is not available (tried: docker compose version)
    echo Update Docker Desktop to a version that includes Compose v2
    pause
    exit /b 1
)

echo [INFO] Docker Compose found
docker compose version
echo.

REM Create .env if not exists
if not exist "backend\.env" (
    echo [INFO] Creating .env file...
    copy backend\env.example backend\.env
    echo [SUCCESS] .env file created
    echo [IMPORTANT] Please edit backend\.env and add your BOT_TOKEN and ADMIN_IDS
) else (
    echo [INFO] backend\.env already exists
)

REM Build the image (migrations run automatically on container start, not here)
echo.
echo [INFO] Building Docker image...
docker compose build

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit backend\.env with your BOT_TOKEN and ADMIN_IDS
echo 2. Run the bot with: run_bot.bat
echo.
echo For a local PostgreSQL instead of an external database, see docs/DOCKER.md
echo.

pause
