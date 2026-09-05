"""
Core AI Sovereign Life OS - Interactive Console Entry Point.
Delegates to unified main.py command terminal for single source of truth.
"""
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from main import main

if __name__ == "__main__":
    main()
