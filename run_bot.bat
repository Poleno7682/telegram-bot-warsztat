@echo off
REM Telegram Bot Launcher for Windows
REM This script runs the bot with proper environment

echo ========================================
echo    Telegram Bot - Auto Service
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "backend\venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call backend\venv\Scripts\activate.bat

REM Check if .env exists
if not exist "backend\.env" (
    echo [ERROR] Configuration file .env not found!
    echo Please copy backend\env.example to backend\.env and configure it
    pause
    exit /b 1
)

REM Run the bot
echo [INFO] Starting bot...
echo.
python run_bot.py

REM Deactivate on exit
deactivate

pause

