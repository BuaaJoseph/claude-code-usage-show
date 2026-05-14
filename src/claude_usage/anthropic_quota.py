"""Fetch authoritative quota percentages from Anthropic's OAuth usage endpoint.

The Claude Code CLI's `/usage` slash command, the v2.1.80+ statusline stdin
`rate_limits` field, and the Claude.ai web UI all source their numbers from a
server-side counter that Anthropic exposes at

    GET https://api.anthropic.com/api/oauth/usage
    Authorization: Bearer <accessToken from ~/.claude/.credentials.json>

The response shape currently shipping (per the v2.1.80 statusline payload
documented in anthropics/claude-code#34074) is:

    {
      "five_hour": {"used_percentage": float, "resets_at": unix_seconds},
      "seven_day": {"used_percentage": float, "resets_at": unix_seconds}
    }

The proposed canonical key names from the open tracking issue
anthropics/claude-code#13585 (asking Anthropic to bless a `claude quota --json`
interface) are `quota.session`, `quota.weekly_all`, `quota.weekly_sonnet`. The
Sonnet/Opus split that the Claude.ai web indicator shows after the Nov 24 2025
update isn't in the current endpoint payload yet (issue #12487), so for the
Sonnet-only bar the dashboard still computes a local JSONL estimate.

This module reads the bearer, hits the endpoint with a 4-second timeout and a
30-second in-process TTL cache, and returns the parsed JSON. Every failure
mode (file missing, token expired, network down, non-200, malformed payload)
collapses to `None` so callers can transparently fall back to the local
JSONL-derived estimate already produced by `claude_usage.parser`.

The reference reader of the same endpoint is
https://github.com/ohugonnot/claude-code-statusline. The v2.1.80 statusline
field is consumed by https://github.com/leeguooooo/claude-code-usage-bar. The
community-standard 5-hour cap constants (Pro 44k, Max 5x 88k, Max 20x 220k
non-cached input+output tokens per 5-hour block) come from
https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor and
https://github.com/ryoppippi/ccusage, which both deliberately do *not*
hard-code weekly caps for exactly this reason.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
USER_AGENT = "claude-code-usage-show/0.1 (+local-dashboard)"
ANTHROPIC_VERSION = "2023-06-01"
CACHE_TTL_SECS = 30.0
REQUEST_TIMEOUT_SECS = 4.0

_cache_lock = threading.Lock()
_cache = {"ts": 0.0, "value": None}  # type: ignore[var-annotated]


def _read_access_token() -> Optional[str]:
    """Return the live OAuth access token from Claude Code's credential file.

    The Claude CLI writes the OAuth bundle as JSON to
    `~/.claude/.credentials.json` on Linux and Windows; on macOS the bundle
    additionally lives in the Keychain entry `Claude Code-credentials`, and on
    recent CLI versions the file may be absent if the Keychain is the only
    store. Reading the macOS Keychain from a daemon process requires either a
    user-prompt (the `security` command) or a separate Apple framework, both
    of which are out of scope for a passive web dashboard, so we limit
    ourselves to the JSON file. When it's not there (e.g. raw API-key auth
    via `ANTHROPIC_API_KEY`, or the macOS Keychain-only case), this returns
    `None` and the dashboard falls back to its local JSONL estimate.

    `expiresAt` in the bundle is in unix *milliseconds*. The CLI itself runs
    the refresh-token flow when the access token nears expiry, so a stale
    file simply yields `None` until the user next invokes Claude Code.
    """
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        with open(CREDENTIALS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    bundle = data.get("claudeAiOauth") or data.get("oauth") or {}
    if not isinstance(bundle, dict):
        return None
    token = bundle.get("accessToken") or bundle.get("access_token")
    if not isinstance(token, str) or not token:
        return None
    expires_at = bundle.get("expiresAt") or bundle.get("expires_at")
    if isinstance(expires_at, (int, float)) and expires_at > 0:
        # The field is unix milliseconds in the Claude CLI; some forks store
        # seconds. Auto-detect by magnitude: >10^12 means ms.
        expires_seconds = float(expires_at) / (1000.0 if expires_at > 10 ** 12 else 1.0)
        if expires_seconds < time.time():
            return None
    return token


def _normalize_window(obj) -> Optional[dict]:
    """Coerce one window object from the endpoint into `{used_percentage, resets_at_unix}`.

    Tolerates the percentage being a number or numeric string, and the reset
    timestamp being unix-seconds, unix-milliseconds, or an ISO-8601 string —
    each of which has appeared in different community write-ups of the
    endpoint and statusline payload. Returns `None` when neither field can be
    parsed.
    """
    if not isinstance(obj, dict):
        return None

    pct_raw = obj.get("used_percentage")
    if pct_raw is None:
        pct_raw = obj.get("percentage")
    if pct_raw is None:
        pct_raw = obj.get("percent")
    try:
        pct = float(pct_raw) if pct_raw is not None else None
    except (TypeError, ValueError):
        pct = None
    if pct is not None and pct <= 1.0 and pct >= 0.0 and not isinstance(pct_raw, str):
        # Some upstreams report 0.0-1.0 instead of 0-100; rescale.
        # Only do this when the number is unambiguously a fraction.
        pct = pct * 100.0

    reset_raw = obj.get("resets_at")
    if reset_raw is None:
        reset_raw = obj.get("reset_at") or obj.get("reset") or obj.get("resetsAt")
    reset_unix: Optional[int]
    if isinstance(reset_raw, (int, float)):
        reset_unix = int(reset_raw)
        if reset_unix > 10 ** 12:
            reset_unix //= 1000
    elif isinstance(reset_raw, str) and reset_raw:
        try:
            ts = datetime.fromisoformat(reset_raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            reset_unix = int(ts.timestamp())
        except ValueError:
            reset_unix = None
    else:
        reset_unix = None

    if pct is None and reset_unix is None:
        return None
    return {"used_percentage": pct, "resets_at_unix": reset_unix}


def fetch_anthropic_quota() -> Optional[dict]:
    """Return Anthropic's authoritative quota percentages, or `None` on any failure.

    Output shape (any inner window may be `None` if Anthropic didn't return it):

        {
          "five_hour":        {"used_percentage": float, "resets_at_unix": int} | None,
          "seven_day":        {"used_percentage": float, "resets_at_unix": int} | None,
          "seven_day_sonnet": {"used_percentage": float, "resets_at_unix": int} | None,
          "seven_day_opus":   {"used_percentage": float, "resets_at_unix": int} | None,
          "source": "anthropic_oauth_usage",
          "fetched_at_unix": int,
        }

    Cached in-process for `CACHE_TTL_SECS` (30 s) so the frontend's 60 s poll
    loop generates at most one upstream call per minute. Negative results
    (missing token, network failure) are cached for the same TTL to avoid
    blocking on every request when Anthropic is unreachable.
    """
    now = time.time()
    with _cache_lock:
        cached_ts = _cache["ts"]
        cached_val = _cache["value"]
    if cached_val is not None and (now - cached_ts) < CACHE_TTL_SECS:
        return cached_val  # type: ignore[return-value]
    # Also short-circuit negative-cache: if the last attempt failed recently,
    # don't try again until the TTL expires.
    if cached_val is None and cached_ts > 0.0 and (now - cached_ts) < CACHE_TTL_SECS:
        return None

    token = _read_access_token()
    if not token:
        with _cache_lock:
            _cache["ts"] = now
            _cache["value"] = None
        return None

    req = urllib.request.Request(
        USAGE_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECS) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise urllib.error.HTTPError(
                    USAGE_ENDPOINT, status, f"non-200 ({status})", resp.headers, None
                )
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        # ValueError covers json.JSONDecodeError which inherits from it.
        with _cache_lock:
            _cache["ts"] = now
            _cache["value"] = None
        return None

    if not isinstance(payload, dict):
        with _cache_lock:
            _cache["ts"] = now
            _cache["value"] = None
        return None

    # Future-proof against the canonical key names proposed in issue #13585
    # alongside the current `five_hour`/`seven_day` keys that v2.1.80 ships.
    quota_blob = payload.get("quota") if isinstance(payload.get("quota"), dict) else {}
    five_hour = _normalize_window(
        payload.get("five_hour")
        or payload.get("session")
        or quota_blob.get("session")
        or quota_blob.get("five_hour")
    )
    seven_day = _normalize_window(
        payload.get("seven_day")
        or payload.get("weekly")
        or payload.get("weekly_all")
        or quota_blob.get("weekly")
        or quota_blob.get("weekly_all")
        or quota_blob.get("seven_day")
    )
    seven_day_sonnet = _normalize_window(
        payload.get("seven_day_sonnet")
        or payload.get("weekly_sonnet")
        or quota_blob.get("weekly_sonnet")
        or quota_blob.get("sonnet")
    )
    seven_day_opus = _normalize_window(
        payload.get("seven_day_opus")
        or payload.get("weekly_opus")
        or quota_blob.get("weekly_opus")
        or quota_blob.get("opus")
    )

    if five_hour is None and seven_day is None and seven_day_sonnet is None and seven_day_opus is None:
        result: Optional[dict] = None
    else:
        result = {
            "five_hour": five_hour,
            "seven_day": seven_day,
            "seven_day_sonnet": seven_day_sonnet,
            "seven_day_opus": seven_day_opus,
            "source": "anthropic_oauth_usage",
            "fetched_at_unix": int(now),
        }
    with _cache_lock:
        _cache["ts"] = now
        _cache["value"] = result
    return result
