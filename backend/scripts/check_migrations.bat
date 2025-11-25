@echo off
REM Script to validate Alembic migrations

set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%\..

echo 🔍 Checking Alembic migrations...

cd /d "%BACKEND_DIR%"

REM Check if alembic is available
where alembic >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Alembic not found! Make sure it's installed.
    exit /b 1
)

REM Try to generate SQL for upgrade
alembic upgrade --sql head >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ Migrations are valid!
    exit /b 0
) else (
    echo ❌ Migration check failed!
    alembic upgrade --sql head
    exit /b 1
)

