"""Flask web application for Claude Code Usage Dashboard."""

import sys
import os
import webbrowser
import threading
import argparse
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, send_from_directory

from claude_usage.parser import get_all_usage_data, aggregate_stats, get_active_sessions, get_claude_dir, get_code_lines_stats

# Static folder: in PyInstaller bundle, _MEIPASS points to Contents/Frameworks/
# and static files are at Contents/Frameworks/claude_usage/static/
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _static = os.path.join(sys._MEIPASS, "claude_usage", "static")
else:
    _static = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=_static, static_url_path="/static")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/stats")
def api_stats():
    """Return aggregated usage statistics."""
    claude_dir = get_claude_dir()
    data = get_all_usage_data(claude_dir)
    sessions = data["sessions"]

    now = datetime.now(timezone.utc)

    stats_all = aggregate_stats(sessions)
    stats_30d = aggregate_stats(sessions, start_date=now - timedelta(days=30))
    stats_7d = aggregate_stats(sessions, start_date=now - timedelta(days=7))

    try:
        code_lines = get_code_lines_stats(claude_dir)
    except Exception:
        code_lines = {"daily": {}, "total": 0, "languages": {}}

    stats_all["code_lines"] = code_lines
    stats_30d["code_lines"] = code_lines
    stats_7d["code_lines"] = code_lines

    return jsonify({
        "all": stats_all,
        "30d": stats_30d,
        "7d": stats_7d,
    })


@app.route("/api/realtime")
def api_realtime():
    """Return real-time session data."""
    claude_dir = get_claude_dir()
    active = get_active_sessions(claude_dir)

    for s in active:
        for k, v in s.items():
            if isinstance(v, datetime):
                s[k] = v.isoformat()

    return jsonify({"active_sessions": active})


def main():
    host = "127.0.0.1"
    port = 8907
    no_browser = False

    if not getattr(sys, "frozen", False):
        parser = argparse.ArgumentParser(description="Claude Code Usage Dashboard")
        parser.add_argument("--port", type=int, default=8907)
        parser.add_argument("--host", type=str, default="127.0.0.1")
        parser.add_argument("--no-browser", action="store_true")
        args = parser.parse_args()
        host = args.host
        port = args.port
        no_browser = args.no_browser

    if not no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    print(f"\n  Claude Code Usage Dashboard")
    print(f"  http://{host}:{port}\n")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
