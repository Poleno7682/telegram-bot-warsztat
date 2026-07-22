@echo off
REM Telegram Bot Launcher for Windows (Docker)
REM Builds (if needed) and runs the bot via docker compose, attached to logs.
REM Press Ctrl+C to stop.

echo ========================================
echo    Telegram Bot - Auto Service
echo ========================================
echo.

REM Check Docker
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker / Docker Compose not found!
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Check if .env exists
if not exist "backend\.env" (
    echo [ERROR] Configuration file backend\.env not found!
    echo Please copy backend\env.example to backend\.env and configure it
    pause
    exit /b 1
)

REM Run the bot (foreground; Ctrl+C stops the containers)
echo [INFO] Starting bot...
echo.
docker compose up --build

pause
