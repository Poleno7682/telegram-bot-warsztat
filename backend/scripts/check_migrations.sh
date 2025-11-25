#!/bin/bash
# Script to validate Alembic migrations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔍 Checking Alembic migrations..."

cd "$BACKEND_DIR"

# Check if alembic is available
if ! command -v alembic &> /dev/null; then
    echo "❌ Alembic not found! Make sure it's installed."
    exit 1
fi

# Try to generate SQL for upgrade
if alembic upgrade --sql head > /dev/null 2>&1; then
    echo "✅ Migrations are valid!"
    exit 0
else
    echo "❌ Migration check failed!"
    alembic upgrade --sql head
    exit 1
fi

