"""Load the CMS schema extensions for repository-local Python commands.

Also enables the content visibility and editable daily-update settings layer.
"""
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
    # Keep the existing behavior for unrelated local Python commands.
    pass

# On an actual repository checkout, load the additive extension.  Fail loudly
# if a deploy script encounters a broken extension instead of publishing a
# site with silently missing visibility/schedule protections.
if (TOOLS / "auto_update_ext.py").is_file():
    import auto_update_ext
    auto_update_ext.install()
