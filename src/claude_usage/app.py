"""Flask web application for Claude Code Usage Dashboard."""

import re
import sys
import os
import webbrowser
import threading
import argparse
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, send_from_directory, request

from claude_usage.parser import (
    get_all_usage_data,
    aggregate_stats,
    get_active_sessions,
    get_claude_dir,
    get_code_lines_stats,
    get_session_messages,
)

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
    claude_dir = get_claude_dir()
    active = get_active_sessions(claude_dir)

    for s in active:
        for k, v in s.items():
            if isinstance(v, datetime):
                s[k] = v.isoformat()

    return jsonify({"active_sessions": active})


@app.route("/api/session/<session_id>/messages")
def api_session_messages(session_id):
    if not re.match(r'^[a-f0-9\-]{8,64}$', session_id):
        return jsonify({"error": "invalid session_id"}), 400
    offset = request.args.get("offset", 0, type=int)
    claude_dir = get_claude_dir()
    result = get_session_messages(claude_dir, session_id, offset)
    return jsonify(result)


def _start_flask(host, port):
    """Run Flask server in a background thread."""
    app.run(host=host, port=port, debug=False, use_reloader=False)


def main():
    host = "127.0.0.1"
    port = 8907
    no_browser = False
    use_native = getattr(sys, "frozen", False)

    if not getattr(sys, "frozen", False):
        parser = argparse.ArgumentParser(description="Claude Code Usage Dashboard")
        parser.add_argument("--port", type=int, default=8907)
        parser.add_argument("--host", type=str, default="127.0.0.1")
        parser.add_argument("--no-browser", action="store_true")
        parser.add_argument("--browser", action="store_true", help="Force open in browser instead of native window")
        args = parser.parse_args()
        host = args.host
        port = args.port
        no_browser = args.no_browser
        if args.browser:
            use_native = False

    url = f"http://{host}:{port}"

    if use_native:
        try:
            import webview
            # Start Flask in background thread
            server_thread = threading.Thread(target=_start_flask, args=(host, port), daemon=True)
            server_thread.start()

            # Wait for server to be ready
            import time
            import urllib.request
            for _ in range(50):
                try:
                    urllib.request.urlopen(url, timeout=0.5)
                    break
                except Exception:
                    time.sleep(0.1)

            # Create native window
            webview.create_window(
                "Claude Code Usage",
                url,
                width=1024,
                height=768,
                min_size=(800, 600),
            )
            webview.start()
            return
        except ImportError:
            pass

    # Fallback: browser mode
    if not no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    print(f"\n  Claude Code Usage Dashboard")
    print(f"  {url}\n")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
