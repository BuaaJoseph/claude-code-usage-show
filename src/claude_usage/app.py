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
    get_all_codex_usage_data,
    get_codex_dir,
    get_quota_stats,
)
from claude_usage.anthropic_quota import fetch_anthropic_quota

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
    source = request.args.get("source", "all")
    if source not in ("all", "claude", "codex"):
        source = "all"
    claude_dir = get_claude_dir()
    codex_dir = get_codex_dir()
    sessions: list = []
    if source in ("all", "claude"):
        sessions.extend(get_all_usage_data(claude_dir)["sessions"])
    if source in ("all", "codex"):
        sessions.extend(get_all_codex_usage_data(codex_dir)["sessions"])

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

    return jsonify({"all": stats_all, "30d": stats_30d, "7d": stats_7d})


def _empty_quota(now):
    empty_window = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
        "total_tokens": 0, "started_at": None,
    }
    week_reset = (now + timedelta(days=7)).isoformat()
    return {
        "window_5h": {**empty_window, "resets_at": None, "seconds_to_reset": 0},
        "window_week": {**empty_window, "resets_at": week_reset, "seconds_to_reset": 7 * 86400},
        "window_week_sonnet": {
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "started_at": None, "resets_at": week_reset, "seconds_to_reset": 7 * 86400,
        },
    }


def _overlay_server_window(local_window, server_window, now_unix):
    """Mutate `local_window` in place so its percentage and reset come from Anthropic.

    The local-JSONL fields (input_tokens / output_tokens / total_tokens /
    started_at) stay untouched so the dashboard can still display the raw
    token spend tallied from disk. The percentage field `server_percentage`
    is added (a float 0-100) which the frontend prefers over the
    tokens-vs-cap-heuristic when present, and the `resets_at` / `seconds_to_reset`
    fields are overwritten with Anthropic's authoritative timestamps.
    Returns True iff at least one field was overlaid.
    """
    if not isinstance(local_window, dict) or not isinstance(server_window, dict):
        return False
    touched = False
    pct = server_window.get("used_percentage")
    if isinstance(pct, (int, float)):
        local_window["server_percentage"] = float(pct)
        touched = True
    reset_unix = server_window.get("resets_at_unix")
    if isinstance(reset_unix, (int, float)):
        reset_dt = datetime.fromtimestamp(int(reset_unix), tz=timezone.utc)
        local_window["resets_at"] = reset_dt.isoformat()
        local_window["seconds_to_reset"] = max(0, int(reset_unix - now_unix))
        touched = True
    return touched


@app.route("/api/quota")
def api_quota():
    """Return per-window quota usage.

    The response is always the union of the JSON-shape that
    `claude_usage.parser.get_quota_stats` produces (which counts non-cached
    input+output tokens from the local Claude JSONL files) and, when the
    Anthropic OAuth-usage endpoint is reachable via the bearer in
    `~/.claude/.credentials.json`, an authoritative `server_percentage` and
    accurate `resets_at` overlay on each window. A top-level `sources` dict
    tags which path ("anthropic_oauth_usage" or "local_estimate") supplied
    the percentage for each window so the frontend can label it.

    The Sonnet-only weekly window (`window_week_sonnet`) is always a local
    estimate because Anthropic's endpoint does not yet expose a Sonnet-only
    counter — tracking issue anthropics/claude-code#13585 proposes the key
    name `quota.weekly_sonnet`, and the `claude_usage.anthropic_quota`
    module already handles that key if/when it ships. Until then the Sonnet
    bar reads off the local JSONL filter.
    """
    claude_dir = get_claude_dir()
    now_dt = datetime.now(timezone.utc)
    try:
        data = get_quota_stats(claude_dir)
    except Exception:
        data = _empty_quota(now_dt)

    if "window_week_sonnet" not in data:
        # Defensive: older parser builds may not have the third bucket. Keep
        # the response shape stable for the frontend.
        data["window_week_sonnet"] = _empty_quota(now_dt)["window_week_sonnet"]

    sources = {
        "five_hour": "local_estimate",
        "seven_day": "local_estimate",
        "seven_day_sonnet": "local_estimate",
    }

    server = None
    try:
        server = fetch_anthropic_quota()
    except Exception:
        server = None

    if server is not None:
        now_unix = now_dt.timestamp()
        if _overlay_server_window(data.get("window_5h"), server.get("five_hour"), now_unix):
            sources["five_hour"] = "anthropic_oauth_usage"
        if _overlay_server_window(data.get("window_week"), server.get("seven_day"), now_unix):
            sources["seven_day"] = "anthropic_oauth_usage"
        sd_sonnet = server.get("seven_day_sonnet")
        if sd_sonnet and _overlay_server_window(data.get("window_week_sonnet"), sd_sonnet, now_unix):
            sources["seven_day_sonnet"] = "anthropic_oauth_usage"
        sd_opus = server.get("seven_day_opus")
        if sd_opus is not None:
            # Surface the Opus percentage if Anthropic ever returns it, even
            # though the dashboard doesn't have a dedicated Opus bar yet.
            pct = sd_opus.get("used_percentage")
            reset_unix = sd_opus.get("resets_at_unix")
            data["window_week_opus"] = {
                "server_percentage": float(pct) if isinstance(pct, (int, float)) else None,
                "resets_at": (
                    datetime.fromtimestamp(int(reset_unix), tz=timezone.utc).isoformat()
                    if isinstance(reset_unix, (int, float))
                    else None
                ),
                "seconds_to_reset": (
                    max(0, int(reset_unix - now_unix))
                    if isinstance(reset_unix, (int, float))
                    else 0
                ),
            }
            sources["seven_day_opus"] = "anthropic_oauth_usage"
        data["server_fetched_at"] = server.get("fetched_at_unix")

    data["sources"] = sources
    return jsonify(data)


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
        parser.add_argument("--browser", action="store_true", help="Force open in browser")
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
            server_thread = threading.Thread(target=_start_flask, args=(host, port), daemon=True)
            server_thread.start()
            import time
            import urllib.request
            for _ in range(50):
                try:
                    urllib.request.urlopen(url, timeout=0.5)
                    break
                except Exception:
                    time.sleep(0.1)
            webview.create_window("Claude Code Usage", url, width=1024, height=768, min_size=(800, 600))
            webview.start()
            return
        except ImportError:
            pass

    if not no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    print(f"\n  Claude Code Usage Dashboard")
    print(f"  {url}\n")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
