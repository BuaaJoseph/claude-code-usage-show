"""Flask web application for Claude Code Usage Dashboard."""

import sys
import os
import logging
import webbrowser
import threading
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, send_from_directory


def _find_static_folder() -> str:
    """Find the static folder, checking multiple possible locations."""
    candidates = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
        candidates.append(base / "claude_usage" / "static")
        candidates.append(base / "static")
        candidates.append(base)

    candidates.append(Path(__file__).parent / "static")

    for c in candidates:
        if c.is_dir() and (c / "index.html").exists():
            return str(c)

    return str(candidates[0]) if candidates else str(Path(__file__).parent / "static")


def _setup_logging():
    """Set up file-based logging for the bundled app."""
    if not getattr(sys, "frozen", False):
        return

    log_dir = Path.home() / ".claude-usage-logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    sys.stdout = open(str(log_dir / "stdout.log"), "w")
    sys.stderr = open(str(log_dir / "stderr.log"), "w")


_setup_logging()

from claude_usage.parser import get_all_usage_data, aggregate_stats, get_active_sessions, get_claude_dir, get_code_lines_stats

static_folder = _find_static_folder()
logging.info(f"Static folder: {static_folder}")
logging.info(f"Static folder exists: {os.path.isdir(static_folder)}")
if os.path.isdir(static_folder):
    logging.info(f"Static folder contents: {os.listdir(static_folder)}")

app = Flask(
    __name__,
    static_folder=static_folder,
    static_url_path="/static",
)


@app.route("/")
def index():
    try:
        return send_from_directory(app.static_folder, "index.html")
    except Exception as e:
        logging.error(f"Error serving index.html: {e}")
        return f"Error: static_folder={app.static_folder}, exists={os.path.isdir(app.static_folder)}, error={e}", 500


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

    logging.info(f"Starting server on {host}:{port}")
    print(f"\n  Claude Code Usage Dashboard")
    print(f"  http://{host}:{port}\n")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
