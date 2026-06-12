"""Desktop entry point: starts the local server and opens a browser.

This is what the packaged (PyInstaller) executable runs. It behaves like a
self-contained app — double-click, a browser tab opens at the collection.

Environment overrides:
  COLLECT_HOST       bind address (default 127.0.0.1; set 0.0.0.0 for LAN access)
  COLLECT_PORT       port (default 5000)
  COLLECT_NO_BROWSER set to 1 to skip auto-opening the browser
"""

from __future__ import annotations

import os
import threading
import webbrowser

from .web.app import create_app


def main() -> None:
    host = os.environ.get("COLLECT_HOST", "127.0.0.1")
    port = int(os.environ.get("COLLECT_PORT", "5000"))
    # When bound to all interfaces, the *local* browser still uses localhost.
    browse_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{browse_host}:{port}"

    app = create_app()

    if os.environ.get("COLLECT_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f"\n  collect is running at {url}")
    if host == "0.0.0.0":
        print("  (reachable from other devices on this network at "
              "http://<this-computer-ip>:%d)" % port)
    print("  Close this window or press Ctrl+C to stop.\n")

    # Flask's reloader must stay off in a frozen app.
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
