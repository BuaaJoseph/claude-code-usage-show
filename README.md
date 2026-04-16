# claude-code-usage-show

A dashboard to visualize Claude Code CLI usage statistics. Parses local session data from `~/.claude/` and displays interactive charts and real-time session monitoring.

## Features

- **Overview** - Sessions, messages, tokens, active days, streaks, peak hour, favorite model, and a GitHub-style heatmap
- **Models** - Daily token consumption bar chart with per-model breakdown; model ranking by total token usage
- **Real-time** - Live monitoring of active Claude Code sessions with context usage, subagent tracking, and auto-refresh

## Install

```bash
pip install git+https://github.com/BuaaJoseph/claude-code-usage-show.git
```

## Usage

```bash
claude-usage
```

Options:

```
--port PORT       Port to listen on (default: 8907)
--host HOST       Host to bind to (default: 127.0.0.1)
--no-browser      Don't auto-open browser
```

## Data Source

Reads session data from `~/.claude/projects/*/`, including:
- Session JSONL files with message history and token usage
- Subagent conversation logs
- Active session metadata from `~/.claude/sessions/`

Deduplicates API calls by `requestId` to avoid double-counting tokens from thinking + response records.
