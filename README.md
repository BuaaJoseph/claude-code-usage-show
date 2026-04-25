# claude-code-usage-show

A dashboard to visualize Claude Code CLI usage statistics. Parses local session data from `~/.claude/` and displays interactive charts and real-time session monitoring.

## Features

- **Overview** - Sessions, messages, tokens, active days, streaks, peak hour, favorite model, and a GitHub-style heatmap
- **Models** - Daily token consumption bar chart with per-model breakdown; model ranking by total token usage
- **Real-time** - Live monitoring of active Claude Code sessions with context usage, subagent tracking, and auto-refresh

## Install

### Option 1: Mac App (DMG)

Download the latest `.dmg` from [Releases](https://github.com/BuaaJoseph/claude-code-usage-show/releases), open it, and drag **Claude Code Usage.app** to Applications.

### Option 2: Homebrew Cask

```bash
brew install --cask BuaaJoseph/tap/claude-code-usage
```

### Option 3: pip / pipx (CLI)

```bash
# Recommended (handles PATH automatically)
pipx install git+https://github.com/BuaaJoseph/claude-code-usage-show.git

# Or with pip
pip install git+https://github.com/BuaaJoseph/claude-code-usage-show.git
```

If `pipx` is not installed: `brew install pipx && pipx ensurepath`

> If `claude-usage` command is not found after `pip install`, run as module instead: `python3 -m claude_usage`

## Usage

**Mac App:** Double-click to open, dashboard appears in your browser automatically.

**CLI:**

```bash
claude-usage              # or: python3 -m claude_usage
```

Options:

```
--port PORT       Port to listen on (default: 8907)
--host HOST       Host to bind to (default: 127.0.0.1)
--no-browser      Don't auto-open browser
```

## Build Mac App from Source

Requires macOS with Python 3.9+.

```bash
git clone https://github.com/BuaaJoseph/claude-code-usage-show.git
cd claude-code-usage-show
bash scripts/build_mac.sh
```

This produces:
- `dist/Claude Code Usage.app` - the Mac app
- `dist/Claude-Code-Usage-0.1.0.dmg` - the DMG installer

To build the DMG with a nice drag-to-Applications layout, install `create-dmg` first: `brew install create-dmg`

## Data Source

Reads session data from `~/.claude/projects/*/`, including:
- Session JSONL files with message history and token usage
- Subagent conversation logs
- Active session metadata from `~/.claude/sessions/`

Deduplicates API calls by `requestId` to avoid double-counting tokens from thinking + response records.
