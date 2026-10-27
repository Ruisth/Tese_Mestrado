"""Shared test configuration: make src/ packages importable without install."""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

SCHEMA_DIR = SRC_DIR / "schemas"
THINGS_DIR = SRC_DIR / "things"
