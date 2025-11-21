@echo off
REM Windows Setup Script for Telegram Bot
REM This script sets up the development environment

echo ========================================
echo    Telegram Bot - Setup (Windows)
echo ========================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.11 or higher
    pause
    exit /b 1
)

echo [INFO] Python found
python --version
echo.

REM Create virtual environment
if not exist "backend\venv" (
    echo [INFO] Creating virtual environment...
    cd backend
    python -m venv venv
    cd ..
    echo [SUCCESS] Virtual environment created
) else (
    echo [INFO] Virtual environment already exists
)

echo.
echo [INFO] Activating virtual environment...
call backend\venv\Scripts\activate.bat

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo [INFO] Installing requirements...
pip install -r backend\requirements.txt

REM Create .env if not exists
if not exist "backend\.env" (
    echo [INFO] Creating .env file...
    copy backend\env.example backend\.env
    echo [SUCCESS] .env file created
    echo [IMPORTANT] Please edit backend\.env and add your BOT_TOKEN and ADMIN_IDS
) else (
    echo [INFO] .env file already exists
)

REM Create db directory
if not exist "backend\db" (
    echo [INFO] Creating database directory...
    mkdir backend\db
)

REM Run migrations
echo [INFO] Running database migrations...
cd backend
alembic upgrade head
cd ..

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit backend\.env with your BOT_TOKEN and ADMIN_IDS
echo 2. Run the bot with: run_bot.bat
echo.

deactivate
pause

