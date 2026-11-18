"""Test suite for Lab 7 - Agentic Node Graph."""

from pathlib import Path
import sys

# Ensure Lab 7 root is on sys.path regardless of execution working directory
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)
