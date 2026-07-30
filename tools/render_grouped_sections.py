#!/usr/bin/env python3
"""Compatibility wrapper for the schema 3 category renderer.

Publication and teaching groups are now ordinary managed categories, so the
single site builder renders them together with every other page category.
"""
from __future__ import annotations

import build_site


def main() -> None:
    data = build_site.load_data()
    build_site.build(build_site.site_today(data), update_date=False)
    print("Rendered managed page categories for website.")


if __name__ == "__main__":
    main()
