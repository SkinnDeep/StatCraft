"""StatCraft Desktop Entry Point."""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from statcraft.modern_app import main

if __name__ == "__main__":
    raise SystemExit(main())
