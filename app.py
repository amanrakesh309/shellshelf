"""ShellShelf entry point: `python3 app.py [--port N]`."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shellshelf.server import serve  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ShellShelf launcher (local app)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser tab")
    args = parser.parse_args()
    server = serve(port=args.port)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"ShellShelf running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:  # headless environments
            print(f"Could not open a browser automatically: {exc}")
            print("Open the URL above manually.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
