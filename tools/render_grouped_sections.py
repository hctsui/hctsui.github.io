#!/usr/bin/env python3
"""Compatibility wrapper for the schema 3 category renderer.

Publication and teaching groups are now ordinary managed categories, so the
single site builder renders them together with every other page category.

This wrapper calls ``build_site.build()`` a second time during deploy. It must
therefore install the same CMS/build-site patches as the primary build step;
otherwise that second build can silently undo post-build behavior such as the
homepage-Upcoming exclusion from the Activities page.
"""
from __future__ import annotations

import cms_extensions
import r2_build_fix

# Install category/schema extensions before importing build_site so its
# ``from category_config import ...`` bindings see the extended functions.
cms_extensions.install()

import build_site

# Keep this secondary build behavior-identical to the primary
# ``run_with_extensions.py tools/build_site.py`` invocation. Both patchers are
# idempotent, so this is also safe if a caller already installed them.
cms_extensions.patch_build_site(build_site)
r2_build_fix.patch_build_site(build_site)


def main() -> None:
    data = build_site.load_data()
    build_site.build(build_site.site_today(data), update_date=False)
    print("Rendered managed page categories for website.")


if __name__ == "__main__":
    main()
