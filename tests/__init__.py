"""Test suite for NaturSQL."""

import os
import sys
from pathlib import Path


os.environ.setdefault("DB_NAME", "appia_test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))