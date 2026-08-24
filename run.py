# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Быстрый старт Zelvera: python run.py"""
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"

if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
