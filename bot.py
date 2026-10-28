import os
import sys
import asyncio

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from nutrition_bot.bot import main

if __name__ == '__main__':
    asyncio.run(main())
