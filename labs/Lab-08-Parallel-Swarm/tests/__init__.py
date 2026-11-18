"""Test suite package for Lab 8 - Parallel Swarm."""

from pathlib import Path
import sys

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)
