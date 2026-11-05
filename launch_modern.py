"""StatCraft Desktop Entry Point."""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from statcraft.modern_app import main

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--verify-local-integrations":
        from statcraft.local_integrations_smoke import verify
        raise SystemExit(verify(*sys.argv[2:]))
    raise SystemExit(main())
