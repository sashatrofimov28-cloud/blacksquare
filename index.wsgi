import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_ACTIVATE = os.path.join(PROJECT_ROOT, "venv", "bin", "activate_this.py")

if os.path.exists(VENV_ACTIVATE):
    with open(VENV_ACTIVATE, encoding="utf-8") as activate_file:
        exec(activate_file.read(), {"__file__": VENV_ACTIVATE})

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app as application
