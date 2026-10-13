"""Zipapp entry point so `python3 -m zipapp` produces a runnable `shellshelf.pyz`."""

from app import main

if __name__ == "__main__":
    raise SystemExit(main())
