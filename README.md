# claude-code-usage-show

[中文](#中文) | [English](#english)

---

<a id="中文"></a>

一个用于可视化 Claude Code CLI 使用数据的仪表盘工具。解析本地 `~/.claude/` 目录下的会话数据，展示交互式图表和实时会话监控。

## 功能

- **Overview（概览）** - 会话数、消息数、Token 总量、活跃天数、连续使用天数、高峰时段、常用模型、GitHub 风格热力图
- **Models（模型）** - 按日展示 Token 消耗柱状图，支持按模型拆分；模型使用排行榜
- **Code（代码）** - AI 每日编写的代码行数统计，按编程语言分组
- **Real-time（实时）** - 实时监控当前活跃的 Claude Code 会话，包括上下文使用率、子代理数量等

## 安装

### 方式一：Mac App（DMG 安装包）

从 [Releases](https://github.com/BuaaJoseph/claude-code-usage-show/releases) 下载最新的 `.dmg` 文件，打开后将 **Claude Code Usage.app** 拖入「应用程序」文件夹。

### 方式二：Homebrew Cask

```bash
brew install --cask BuaaJoseph/tap/claude-code-usage
```

### 方式三：pip / pipx（命令行）

```bash
# 推荐（自动处理 PATH）
pipx install git+https://github.com/BuaaJoseph/claude-code-usage-show.git

# 或使用 pip
pip install git+https://github.com/BuaaJoseph/claude-code-usage-show.git
```

如果没有安装 `pipx`：`brew install pipx && pipx ensurepath`

> 如果 `pip install` 后找不到 `claude-usage` 命令，可以用模块方式运行：`python3 -m claude_usage`

## 使用

**Mac App：** 双击打开，仪表盘会在原生窗口中展示。

**命令行：**

```bash
claude-usage              # 或：python3 -m claude_usage
```

参数说明：

```
--port PORT       监听端口（默认：8907）
--host HOST       绑定地址（默认：127.0.0.1）
--no-browser      不自动打开浏览器
--browser         强制使用浏览器打开（而非原生窗口）
```

## 从源码构建 Mac App

需要 macOS + Python 3.9+。

```bash
git clone https://github.com/BuaaJoseph/claude-code-usage-show.git
cd claude-code-usage-show
bash scripts/build_mac.sh
```

构建产物：
- `dist/Claude Code Usage.app` - Mac 应用
- `dist/Claude-Code-Usage-x.x.x.dmg` - DMG 安装包

## 数据来源

读取 `~/.claude/projects/*/` 下的会话数据，包括：
- JSONL 格式的会话日志（消息记录与 Token 用量）
- 子代理（Subagent）对话日志
- `~/.claude/sessions/` 下的活跃会话元数据

通过 `requestId` 去重，避免 thinking + response 双条记录导致的 Token 重复计算。

---

<a id="english"></a>

# claude-code-usage-show

A dashboard to visualize Claude Code CLI usage statistics. Parses local session data from `~/.claude/` and displays interactive charts and real-time session monitoring.

## Features

- **Overview** - Sessions, messages, tokens, active days, streaks, peak hour, favorite model, and a GitHub-style heatmap
- **Models** - Daily token consumption bar chart with per-model breakdown; model ranking by total token usage
- **Code** - Daily code lines written by AI, grouped by programming language
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

**Mac App:** Double-click to open, dashboard appears in a native window.

**CLI:**

```bash
claude-usage              # or: python3 -m claude_usage
```

Options:

```
--port PORT       Port to listen on (default: 8907)
--host HOST       Host to bind to (default: 127.0.0.1)
--no-browser      Don't auto-open browser
--browser         Force open in browser instead of native window
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
- `dist/Claude-Code-Usage-x.x.x.dmg` - the DMG installer

## Data Source

Reads session data from `~/.claude/projects/*/`, including:
- Session JSONL files with message history and token usage
- Subagent conversation logs
- Active session metadata from `~/.claude/sessions/`

Deduplicates API calls by `requestId` to avoid double-counting tokens from thinking + response records.
