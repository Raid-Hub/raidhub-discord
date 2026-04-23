"""
Structured logging aligned with RaidHub-Services (Go) and RaidHub-API (TypeScript).

Format: ``{RFC3339Nano} [{LEVEL}][{prefix}] -- {LOG_KEY}`` or with fields:
``... {LOG_KEY} >> field=value ...`` (keys sorted, logfmt-style quoting).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, TextIO

_LOG_LEVEL_PRIORITY = {"debug": 0, "info": 1, "warn": 2, "error": 3}

_LEVEL_DEBUG = "DEBUG"
_LEVEL_INFO = "INFO"
_LEVEL_WARN = "WARN"
_LEVEL_ERROR = "ERROR"
_LEVEL_FATAL = "FATAL"


def _env_log_level() -> str:
    raw = (os.getenv("LOG_LEVEL") or "info").strip().lower()
    return raw if raw in _LOG_LEVEL_PRIORITY else "info"


def _should_log(level: str) -> bool:
    current = _LOG_LEVEL_PRIORITY.get(_env_log_level(), 1)
    return _LOG_LEVEL_PRIORITY.get(level.lower(), 1) >= current


def _format_logfmt_key(key: str) -> str:
    if key.startswith("$"):
        return key[1:]
    return key


def _format_logfmt_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        s = str(value)
    elif isinstance(value, (dict, list, tuple)):
        s = json.dumps(value, separators=(",", ":"), default=str)
    else:
        s = str(value)

    needs_quoting = any(r <= " " or r in "=\"\\" for r in s)
    if needs_quoting:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _timestamp_utc() -> str:
    # Match Go RFC3339Nano-style UTC (microsecond precision; Python has no true ns in datetime).
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


class Logger:
    """Namespaced logger; construct only via ``src.log`` (``ingress``, ``raidhub_api``, …)."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def _emit(self, level: str, stream: TextIO, key: str, fields: dict[str, Any]) -> None:
        ts = _timestamp_utc()
        prefix = f"{ts} [{level}][{self.prefix}] -- "
        if not fields:
            line = f"{prefix}{key}\n"
        else:
            parts = [f"{_format_logfmt_key(k)}={_format_logfmt_value(fields[k])}" for k in sorted(fields)]
            line = f"{prefix}{key} >> " + " ".join(parts) + "\n"
        stream.write(line)
        stream.flush()

    def debug(self, key: str, fields: dict[str, Any] | None = None) -> None:
        if not _should_log("debug"):
            return
        self._emit(_LEVEL_DEBUG, sys.stdout, key, dict(fields or {}))

    def info(self, key: str, fields: dict[str, Any] | None = None) -> None:
        if not _should_log("info"):
            return
        self._emit(_LEVEL_INFO, sys.stdout, key, dict(fields or {}))

    def warn(self, key: str, err: BaseException | None, fields: dict[str, Any] | None = None) -> None:
        if not _should_log("warn"):
            return
        merged = dict(fields or {})
        merged["error"] = str(err) if err else "<nil>"
        self._emit(_LEVEL_WARN, sys.stderr, key, merged)

    def error(self, key: str, err: BaseException, fields: dict[str, Any] | None = None) -> None:
        if not _should_log("error"):
            return
        merged = dict(fields or {})
        merged["error"] = str(err)
        self._emit(_LEVEL_ERROR, sys.stderr, key, merged)

    def fatal(self, key: str, err: BaseException | None, fields: dict[str, Any] | None = None) -> None:
        merged = dict(fields or {})
        merged["error"] = str(err) if err else "<nil>"
        self._emit(_LEVEL_FATAL, sys.stderr, key, merged)
        raise SystemExit(1)
