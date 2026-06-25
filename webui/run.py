"""Convenience launcher for the GR8T web UI.

    python webui/run.py            # http://127.0.0.1:5000
    PORT=5050 python webui/run.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from webui.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    # auto-reload templates so edits show up without a manual restart
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.run(host=host, port=port, debug=False, use_reloader=False)
