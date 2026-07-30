#!/usr/bin/env python3
"""Compatibility entry point; all logic now lives in process_request.py."""
from process_request import *  # noqa: F401,F403
from process_request import main

if __name__ == "__main__":
    main()
