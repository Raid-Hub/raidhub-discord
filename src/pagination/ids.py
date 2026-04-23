from __future__ import annotations


def parse_pager_custom_id(custom_id: str) -> tuple[str, str, str] | None:
    parts = custom_id.split(":", 2)
    if len(parts) != 3:
        return None
    prefix, session_id, nav_token = parts[0], parts[1], parts[2]
    if not prefix or not session_id:
        return None
    return prefix, session_id, nav_token


def pager_custom_id(prefix: str, session_id: str, nav_token: str) -> str:
    return f"{prefix}:{session_id}:{nav_token}"
