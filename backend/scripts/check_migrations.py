#!/usr/bin/env python3
"""Script to validate Alembic migrations"""

import sys
import subprocess
from pathlib import Path


def check_migrations():
    """Check if migrations can be applied without errors"""
    backend_dir = Path(__file__).parent.parent
    
    print("🔍 Checking Alembic migrations...")
    
    # Try to generate SQL for upgrade
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "--sql", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Migrations are valid!")
        print(f"📝 Generated SQL ({len(result.stdout)} characters)")
        return 0
    except subprocess.CalledProcessError as e:
        print("❌ Migration check failed!")
        print(f"Error: {e.stderr}")
        return 1
    except FileNotFoundError:
        print("❌ Alembic not found! Make sure it's installed.")
        return 1


if __name__ == "__main__":
    sys.exit(check_migrations())

