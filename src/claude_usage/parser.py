"""Parse Claude Code CLI local data files."""

import json
import os
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict
from pathlib import Path

import psutil


def get_claude_dir() -> Path:
    """Get the Claude Code data directory."""
    return Path.home() / ".claude"


def parse_sessions_metadata(claude_dir: Path) -> dict[str, dict]:
    """Parse session metadata from ~/.claude/sessions/*.json."""
    sessions = {}
    sessions_dir = claude_dir / "sessions"
    if not sessions_dir.exists():
        return sessions

    for f in sessions_dir.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
                sid = data.get("sessionId", "")
                if sid:
                    sessions[sid] = {
                        "pid": data.get("pid"),
                        "sessionId": sid,
                        "cwd": data.get("cwd", ""),
                        "startedAt": data.get("startedAt", 0),
                        "kind": data.get("kind", ""),
                        "entrypoint": data.get("entrypoint", ""),
                    }
        except (json.JSONDecodeError, IOError):
            continue
    return sessions


def parse_jsonl_file(filepath: str) -> dict:
    """Parse a single JSONL session file and extract usage data."""
    session_data = {
        "session_id": "",
        "messages": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "models": defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "count": 0}),
        "start_time": None,
        "end_time": None,
        "message_count": 0,
        "user_message_count": 0,
        "assistant_message_count": 0,
        "timestamps": [],
    }

    # Track seen requestIds to avoid double-counting tokens.
    # A single API call can produce two JSONL records (thinking + text/tool_use)
    # with identical usage data, so we must deduplicate.
    seen_request_ids: set[str] = set()

    def _process_lines(fpath: str) -> None:
        try:
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    record_type = record.get("type", "")
                    timestamp_str = record.get("timestamp", "")
                    session_id = record.get("sessionId", "")

                    if session_id and not session_data["session_id"]:
                        session_data["session_id"] = session_id

                    if timestamp_str:
                        try:
                            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                            if session_data["start_time"] is None or ts < session_data["start_time"]:
                                session_data["start_time"] = ts
                            if session_data["end_time"] is None or ts > session_data["end_time"]:
                                session_data["end_time"] = ts
                        except ValueError:
                            pass

                    if record_type == "user":
                        session_data["user_message_count"] += 1
                        session_data["message_count"] += 1
                        if timestamp_str:
                            session_data["timestamps"].append(timestamp_str)

                    elif record_type == "assistant":
                        session_data["assistant_message_count"] += 1
                        session_data["message_count"] += 1

                        # Deduplicate by requestId to avoid double-counting
                        request_id = record.get("requestId", "")
                        if request_id and request_id in seen_request_ids:
                            if timestamp_str:
                                session_data["timestamps"].append(timestamp_str)
                            continue
                        if request_id:
                            seen_request_ids.add(request_id)

                        msg = record.get("message", {})
                        usage = msg.get("usage", {})
                        model = msg.get("model", "unknown")
                        if model == "<synthetic>":
                            continue

                        input_tokens = usage.get("input_tokens", 0)
                        cache_creation = usage.get("cache_creation_input_tokens", 0)
                        cache_read = usage.get("cache_read_input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)

                        total_input = input_tokens + cache_creation + cache_read

                        session_data["total_input_tokens"] += total_input
                        session_data["total_output_tokens"] += output_tokens

                        session_data["models"][model]["input_tokens"] += total_input
                        session_data["models"][model]["output_tokens"] += output_tokens
                        session_data["models"][model]["count"] += 1

                        if timestamp_str:
                            session_data["timestamps"].append(timestamp_str)
        except IOError:
            pass

    # Parse main session file
    _process_lines(filepath)

    # Also parse subagent files for this session
    session_id = Path(filepath).stem
    subagent_dir = Path(filepath).parent / session_id / "subagents"
    if subagent_dir.is_dir():
        for sub_jsonl in subagent_dir.glob("agent-*.jsonl"):
            _process_lines(str(sub_jsonl))

    return session_data


def find_all_session_files(claude_dir: Path) -> list[str]:
    """Find all JSONL session files across all projects."""
    files = []
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return files

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            # Skip subagent files
            if "/subagents/" in str(jsonl_file):
                continue
            files.append(str(jsonl_file))

    return files


def get_all_usage_data(claude_dir: Optional[Path] = None) -> dict:
    """Parse all session data and return aggregated usage info."""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    session_files = find_all_session_files(claude_dir)
    sessions_meta = parse_sessions_metadata(claude_dir)
    all_sessions = []

    for filepath in session_files:
        session_data = parse_jsonl_file(filepath)
        if session_data["message_count"] == 0:
            continue

        # Attach project info from filepath
        parts = Path(filepath).parts
        project_idx = parts.index("projects") if "projects" in parts else -1
        project_name = parts[project_idx + 1] if project_idx >= 0 and project_idx + 1 < len(parts) else "unknown"

        session_data["project"] = project_name
        session_data["filepath"] = filepath

        # Merge metadata if available
        sid = session_data["session_id"]
        if sid in sessions_meta:
            meta = sessions_meta[sid]
            session_data["cwd"] = meta.get("cwd", "")
            session_data["kind"] = meta.get("kind", "")
            session_data["entrypoint"] = meta.get("entrypoint", "")
            if meta.get("startedAt"):
                session_data["started_at_epoch"] = meta["startedAt"]

        # Convert defaultdict to regular dict for JSON serialization
        session_data["models"] = dict(session_data["models"])

        all_sessions.append(session_data)

    return {"sessions": all_sessions}


def aggregate_stats(sessions: list[dict], start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> dict:
    """Aggregate statistics from sessions within a date range."""
    filtered = []
    for s in sessions:
        if s.get("start_time") is None:
            continue
        st = s["start_time"]
        if start_date and st < start_date:
            continue
        if end_date and st > end_date:
            continue
        filtered.append(s)

    total_sessions = len(filtered)
    total_messages = sum(s["message_count"] for s in filtered)
    total_input_tokens = sum(s["total_input_tokens"] for s in filtered)
    total_output_tokens = sum(s["total_output_tokens"] for s in filtered)
    total_tokens = total_input_tokens + total_output_tokens

    # Active days
    active_dates = set()
    all_hours = defaultdict(int)
    for s in filtered:
        if s.get("start_time"):
            d = s["start_time"].date()
            active_dates.add(d)
        for ts_str in s.get("timestamps", []):
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                active_dates.add(ts.date())
                all_hours[ts.hour] += 1
            except ValueError:
                pass

    active_days = len(active_dates)

    # Streaks
    sorted_dates = sorted(active_dates)
    current_streak = 0
    longest_streak = 0
    if sorted_dates:
        streak = 1
        for i in range(1, len(sorted_dates)):
            diff = (sorted_dates[i] - sorted_dates[i - 1]).days
            if diff == 1:
                streak += 1
            else:
                longest_streak = max(longest_streak, streak)
                streak = 1
        longest_streak = max(longest_streak, streak)

        # Current streak: count backward from today/most recent date
        today = datetime.now(timezone.utc).date()
        if sorted_dates[-1] >= today or (today - sorted_dates[-1]).days <= 1:
            current_streak = 1
            for i in range(len(sorted_dates) - 2, -1, -1):
                if (sorted_dates[i + 1] - sorted_dates[i]).days == 1:
                    current_streak += 1
                else:
                    break

    # Peak hour
    peak_hour = max(all_hours, key=all_hours.get) if all_hours else 0

    # Models aggregation
    models_agg: dict[str, dict[str, int]] = {}
    for s in filtered:
        for model, data in s.get("models", {}).items():
            if model == "<synthetic>":
                continue
            if model not in models_agg:
                models_agg[model] = {"input_tokens": 0, "output_tokens": 0, "count": 0}
            models_agg[model]["input_tokens"] += data["input_tokens"]
            models_agg[model]["output_tokens"] += data["output_tokens"]
            models_agg[model]["count"] += data["count"]

    # Favorite model
    favorite_model = ""
    if models_agg:
        favorite_model = max(
            models_agg,
            key=lambda m: models_agg[m]["input_tokens"] + models_agg[m]["output_tokens"],
        )

    # Daily token breakdown
    daily_tokens: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0})
    )
    for s in filtered:
        date_str = s["start_time"].strftime("%Y-%m-%d") if s.get("start_time") else "unknown"
        for model, data in s.get("models", {}).items():
            if model == "<synthetic>":
                continue
            daily_tokens[date_str][model]["input_tokens"] += data["input_tokens"]
            daily_tokens[date_str][model]["output_tokens"] += data["output_tokens"]

    # Convert to serializable
    daily_tokens_out = {}
    for date, models in sorted(daily_tokens.items()):
        daily_tokens_out[date] = {m: dict(v) for m, v in models.items()}

    # Heatmap data: date -> message count
    heatmap: dict[str, int] = defaultdict(int)
    for s in filtered:
        for ts_str in s.get("timestamps", []):
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                heatmap[ts.date().isoformat()] += 1
            except ValueError:
                pass

    # Models sorted by total tokens descending
    models_sorted = sorted(
        [
            {
                "model": m,
                "input_tokens": d["input_tokens"],
                "output_tokens": d["output_tokens"],
                "total_tokens": d["input_tokens"] + d["output_tokens"],
                "percentage": round(
                    (d["input_tokens"] + d["output_tokens"]) / total_tokens * 100, 1
                )
                if total_tokens > 0
                else 0,
            }
            for m, d in models_agg.items()
        ],
        key=lambda x: x["total_tokens"],
        reverse=True,
    )

    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "active_days": active_days,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "peak_hour": peak_hour,
        "favorite_model": favorite_model,
        "models": models_sorted,
        "daily_tokens": daily_tokens_out,
        "heatmap": dict(heatmap),
    }


def get_active_sessions(claude_dir: Optional[Path] = None) -> list[dict]:
    """Get currently active Claude Code sessions."""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    active = []
    sessions_dir = claude_dir / "sessions"
    if not sessions_dir.exists():
        return active

    for f in sessions_dir.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
            pid = data.get("pid")
            if pid and psutil.pid_exists(pid):
                session_id = data.get("sessionId", "")
                cwd = data.get("cwd", "")
                started_at = data.get("startedAt", 0)
                kind = data.get("kind", "")
                entrypoint = data.get("entrypoint", "")

                session_info = {
                    "pid": pid,
                    "session_id": session_id,
                    "cwd": cwd,
                    "started_at": started_at,
                    "kind": kind,
                    "entrypoint": entrypoint,
                    "is_alive": True,
                }

                # Find and parse the session's JSONL for real-time info
                projects_dir = claude_dir / "projects"
                if projects_dir.exists():
                    for jsonl_file in projects_dir.rglob(f"{session_id}.jsonl"):
                        rt_data = _parse_realtime_data(str(jsonl_file))
                        session_info.update(rt_data)
                        break

                # Count subagents
                for project_dir in (claude_dir / "projects").iterdir():
                    sub_dir = project_dir / session_id / "subagents"
                    if sub_dir.exists():
                        agent_metas = list(sub_dir.glob("*.meta.json"))
                        session_info["subagent_count"] = len(agent_metas)
                        session_info["subagents"] = []
                        for meta_file in agent_metas:
                            try:
                                with open(meta_file) as mf:
                                    meta = json.load(mf)
                                    session_info["subagents"].append(meta)
                            except (json.JSONDecodeError, IOError):
                                pass
                        break

                active.append(session_info)
        except (json.JSONDecodeError, IOError):
            continue

    return active


def _parse_realtime_data(filepath: str) -> dict:
    """Parse a session JSONL for real-time display data."""
    data = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "message_count": 0,
        "user_message_count": 0,
        "assistant_message_count": 0,
        "models_used": defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0}),
        "last_model": "",
        "last_activity": "",
        "version": "",
        "git_branch": "",
    }

    context_window = 200000
    last_input = 0

    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                record_type = record.get("type", "")

                if record_type == "user":
                    data["user_message_count"] += 1
                    data["message_count"] += 1
                    data["last_activity"] = record.get("timestamp", "")
                    data["version"] = record.get("version", data["version"])
                    data["git_branch"] = record.get("gitBranch", data["git_branch"])

                elif record_type == "assistant":
                    data["assistant_message_count"] += 1
                    data["message_count"] += 1
                    msg = record.get("message", {})
                    usage = msg.get("usage", {})
                    model = msg.get("model", "unknown")
                    if model == "<synthetic>":
                        continue
                    data["last_model"] = model
                    data["last_activity"] = record.get("timestamp", "")

                    input_tokens = (
                        usage.get("input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                    )
                    output_tokens = usage.get("output_tokens", 0)

                    data["total_input_tokens"] += input_tokens
                    data["total_output_tokens"] += output_tokens
                    data["models_used"][model]["input_tokens"] += input_tokens
                    data["models_used"][model]["output_tokens"] += output_tokens

                    if input_tokens > 0:
                        last_input = input_tokens

    except IOError:
        pass

    data["context_used"] = last_input
    data["context_window"] = context_window
    data["context_percentage"] = round(last_input / context_window * 100, 1) if context_window else 0
    data["models_used"] = {k: dict(v) for k, v in data["models_used"].items()}
    return data


def get_session_messages(claude_dir: Path, session_id: str, offset: int = 0) -> dict:
    """Read messages from a session JSONL file starting from line offset.

    Returns structured messages suitable for the detail view, merging
    assistant content blocks that share the same requestId.
    """
    projects_dir = claude_dir / "projects"
    jsonl_path: Optional[Path] = None
    for f in projects_dir.rglob(f"{session_id}.jsonl"):
        jsonl_path = f
        break

    if not jsonl_path or not jsonl_path.exists():
        return {"messages": [], "offset": offset, "session_id": session_id}

    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
    except IOError:
        return {"messages": [], "offset": offset, "session_id": session_id}

    new_offset = len(all_lines)
    messages: list[dict] = []
    request_map: dict[str, int] = {}  # requestId -> index in messages

    for line in all_lines[offset:]:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        record_type = record.get("type", "")

        if record_type == "user":
            msg = record.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                if not content.strip():
                    continue
                content = [{"type": "text", "text": content}]
            elif not content:
                continue
            messages.append({
                "type": "user",
                "timestamp": record.get("timestamp", ""),
                "uuid": record.get("uuid", ""),
                "content": content,
            })

        elif record_type == "assistant":
            request_id = record.get("requestId", "")
            msg = record.get("message", {})
            model = msg.get("model", "")
            if model == "<synthetic>":
                continue

            content_blocks = msg.get("content", [])
            if not content_blocks:
                continue

            if request_id and request_id in request_map:
                # Merge additional content blocks from same API call
                messages[request_map[request_id]]["content"].extend(content_blocks)
            else:
                usage = msg.get("usage", {})
                total_in = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                )
                entry: dict = {
                    "type": "assistant",
                    "timestamp": record.get("timestamp", ""),
                    "requestId": request_id,
                    "model": model,
                    "stop_reason": msg.get("stop_reason", ""),
                    "usage": {
                        "input_tokens": total_in,
                        "output_tokens": usage.get("output_tokens", 0),
                    },
                    "content": list(content_blocks),
                }
                if request_id:
                    request_map[request_id] = len(messages)
                messages.append(entry)

    return {
        "messages": messages,
        "offset": new_offset,
        "session_id": session_id,
    }


def format_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# ---------- Git Code Lines Stats ----------

LANG_EXTENSIONS = {
    "JavaScript": [".js", ".jsx", ".mjs", ".cjs"],
    "TypeScript": [".ts", ".tsx"],
    "Python": [".py"],
    "Java": [".java"],
    "Go": [".go"],
    "Rust": [".rs"],
    "C/C++": [".c", ".cpp", ".h", ".hpp", ".cc", ".cxx"],
    "Swift": [".swift"],
    "Kotlin": [".kt", ".kts"],
    "Ruby": [".rb"],
    "PHP": [".php"],
    "Shell": [".sh", ".bash", ".zsh"],
    "HTML/CSS": [".html", ".htm", ".css", ".scss", ".less", ".sass"],
    "Vue": [".vue"],
    "JSON": [".json"],
    "YAML": [".yaml", ".yml"],
    "Markdown": [".md"],
    "Other": [],
}

EXT_TO_LANG = {}
for lang, exts in LANG_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_LANG[ext] = lang


def _get_lang_for_file(filename: str) -> str:
    _, ext = os.path.splitext(filename.lower())
    return EXT_TO_LANG.get(ext, "Other")


def get_code_lines_stats(claude_dir: Optional[Path] = None) -> dict:
    """Parse Claude Code JSONL logs to get daily code lines written by AI, grouped by language."""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return {"daily": {}, "total": 0, "languages": {}}

    daily: dict[str, dict[str, int]] = {}

    for jsonl_file in projects_dir.rglob("*.jsonl"):
        if "/subagents/" in str(jsonl_file):
            continue

        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if record.get("type") != "assistant":
                        continue

                    timestamp_str = record.get("timestamp", "")
                    if not timestamp_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        date_str = ts.strftime("%Y-%m-%d")
                    except ValueError:
                        continue

                    for content in record.get("message", {}).get("content", []):
                        if content.get("type") != "tool_use":
                            continue

                        tool_name = content.get("name", "")
                        tool_input = content.get("input", {})

                        if tool_name == "Write":
                            file_path = tool_input.get("file_path", "")
                            content_text = tool_input.get("content", "")
                            if file_path and content_text:
                                lines_count = len(content_text.split("\n"))
                                lang = _get_lang_for_file(file_path)
                                if lang not in daily.get(date_str, {}):
                                    daily.setdefault(date_str, {})[lang] = 0
                                daily[date_str][lang] += lines_count

                        elif tool_name == "Edit":
                            file_path = tool_input.get("file_path", "")
                            new_string = tool_input.get("new_string", "")
                            old_string = tool_input.get("old_string", "")
                            if file_path and new_string:
                                new_lines = len(new_string.split("\n"))
                                old_lines = len(old_string.split("\n")) if old_string else 0
                                net_lines = new_lines - old_lines
                                lang = _get_lang_for_file(file_path)
                                if lang not in daily.get(date_str, {}):
                                    daily.setdefault(date_str, {})[lang] = 0
                                daily[date_str][lang] += net_lines

        except (IOError, OSError):
            continue

    langs_total: dict[str, int] = {}
    grand_total = 0
    for date_data in daily.values():
        for lang, lines in date_data.items():
            langs_total[lang] = langs_total.get(lang, 0) + lines
            grand_total += lines

    return {
        "daily": daily,
        "total": grand_total,
        "languages": langs_total,
    }
