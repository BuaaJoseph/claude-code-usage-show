# claude-code-usage-show

A dashboard to visualize Claude Code CLI usage statistics. Parses local session data from `~/.claude/` and displays interactive charts and real-time session monitoring.

## Features

- **Overview** - Sessions, messages, tokens, active days, streaks, peak hour, favorite model, and a GitHub-style heatmap
- **Models** - Daily token consumption bar chart with per-model breakdown; model ranking by total token usage
- **Real-time** - Live monitoring of active Claude Code sessions with context usage, subagent tracking, and auto-refresh

## Install

**Recommended (uses [pipx](https://pipx.pypa.io/), handles PATH automatically):**

```bash
pipx install git+https://github.com/BuaaJoseph/claude-code-usage-show.git
```

If you don't have `pipx`: `brew install pipx && pipx ensurepath`

**Alternative (pip):**

```bash
pip install git+https://github.com/BuaaJoseph/claude-code-usage-show.git
```

> Note: On macOS, `pip` may install the `claude-usage` script to a directory that isn't on your `PATH` (e.g. `~/Library/Python/3.x/bin`). If `claude-usage` is not found after install, use one of:
>
> - Run as a module: `python3 -m claude_usage`
> - Find where pip put it: `python3 -m site --user-base` then add `/bin` to your `PATH`
> - Or use `pipx` (recommended above)

## Usage

```bash
claude-usage              # or: python3 -m claude_usage
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
