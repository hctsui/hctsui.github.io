"""Load the CMS schema extensions for repository-local Python commands."""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "tools"
if TOOLS.is_dir() and str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
try:
    import cms_extensions
    cms_extensions.install()
except Exception:
    # Individual wrapper scripts report actionable errors. Keeping this import
    # soft avoids breaking unrelated one-off Python commands in the repository.
    pass
