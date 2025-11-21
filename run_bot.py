#!/usr/bin/env python3
"""
Telegram Bot Launcher
Entry point for running the bot from project root
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import and run the bot
from app.main import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

