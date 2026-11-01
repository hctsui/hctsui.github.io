"""Initialize the site's CMS, visibility and chronological ordering extensions."""
from __future__ import annotations
import sys
from pathlib import Path
TOOLS=Path(__file__).resolve().parent/'tools'
if TOOLS.is_dir() and str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))
try:
    import cms_extensions
    cms_extensions.install()
except Exception:
    # Preserve existing behavior for unrelated local Python commands.
    pass
if (TOOLS/'auto_update_ext.py').is_file():
    import auto_update_ext
    auto_update_ext.install()
if (TOOLS/'chronological_ids.py').is_file():
    import chronological_ids
    chronological_ids.install()

# Canonical item IDs, semantic managed-profile references and atomic rename batches.
if (TOOLS/'item_id_system.py').is_file():
    import item_id_system
    item_id_system.install()
