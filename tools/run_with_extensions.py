#!/usr/bin/env python3
"""Run one existing tool with the non-destructive CMS schema extensions loaded."""
from __future__ import annotations

import argparse
import importlib
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cms_extensions
import r2_build_fix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    target = Path(options.target)
    if not target.is_absolute():
        target = ROOT / target
    if not target.exists():
        raise SystemExit(f"Tool not found: {target}")

    cms_extensions.install()
    sys.argv = [str(target), *options.args]
    if target.name == "build_site.py":
        module = importlib.import_module("build_site")
        cms_extensions.patch_build_site(module)
        r2_build_fix.patch_build_site(module)
        module.main()
        return
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
