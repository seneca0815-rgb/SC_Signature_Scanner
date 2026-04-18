"""Ensure the project root is on sys.path so test modules can import from it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
