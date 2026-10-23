#!/usr/bin/env python3
"""Entry point for the local server and for a hosted one.

Local:   python3 app.py [port]
Hosted:  gunicorn app:app
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.webapp import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = int(os.environ.get("PORT", 8090))
    print("Indian Movies Legacy - Lumia build")
    print("  http://127.0.0.1:%d" % port)
    print("  http://<mac-ip>:%d" % port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
