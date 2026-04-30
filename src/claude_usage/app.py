"""Flask web application for Claude Code Usage Dashboard."""

import sys
import webbrowser
import threading
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _get_base_dir() -> Path:
    """Return the base directory for static assets.

    When running as a PyInstaller bundle, resources live under sys._MEIPASS.
    When running normally, they are next to this file.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "claude_usage"
    return Path(__file__).parent


from flask import Flask, jsonify, send_from_directory

from claude_usage.parser import get_all_usage_data, aggregate_stats, get_active_sessions, get_claude_dir

_base = _get_base_dir()
app = Flask(
    __name__,
    static_folder=str(_base / "static"),
    static_url_path="/static",
)


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
    parser = argparse.ArgumentParser(description="Claude Code Usage Dashboard")
    parser.add_argument("--port", type=int, default=8907, help="Port to listen on (default: 8907)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()

    print(f"\n  Claude Code Usage Dashboard")
    print(f"  http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
