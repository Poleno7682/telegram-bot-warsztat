#!/usr/bin/env python3
"""
Telegram Bot Launcher
Entry point for running the bot from project root
"""

import sys
import os
import asyncio

# Add backend to Python path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_path)

# Import main function from app
from app.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

