from __future__ import annotations

import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..log import pagination as pagination_log
from ..prom_metrics import observe_pager_render_failure
from .ids import parse_pager_custom_id

DEFAULT_SESSION_TTL_SEC = 600.0
DEFAULT_EXPIRED_MESSAGE = "This session expired. Run the command again."

PagerRenderFn = Callable[[dict[str, Any], str, str], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class _PagerRegistration:
    render: PagerRenderFn
    expired_message: str


class InMemoryPagedSessionStore:
    def __init__(self, *, ttl_sec: float = DEFAULT_SESSION_TTL_SEC) -> None:
        self._ttl_sec = ttl_sec
        self._sessions: dict[str, tuple[float, dict[str, Any]]] = {}

    def _purge(self) -> None:
        now = time.time()
        dead = [k for k, (created, _) in self._sessions.items() if now - created > self._ttl_sec]
        for k in dead:
            del self._sessions[k]

    def put(self, state: dict[str, Any]) -> str:
        self._purge()
        session_id = secrets.token_hex(8)
        self._sessions[session_id] = (time.time(), state)
        return session_id

    def get(self, session_id: str) -> dict[str, Any] | None:
        self._purge()
        entry = self._sessions.get(session_id)
        if not entry:
            return None
        return entry[1]


_global_store = InMemoryPagedSessionStore()
_registrations: dict[str, _PagerRegistration] = {}


def default_expired_session_content() -> dict[str, Any]:
    return {"content": DEFAULT_EXPIRED_MESSAGE}


def register_pager(
    prefix: str,
    render: PagerRenderFn,
    *,
    expired_message: str | None = None,
) -> None:
    if ":" in prefix:
        raise ValueError("pager prefix must not contain ':'")
    _registrations[prefix] = _PagerRegistration(
        render=render,
        expired_message=expired_message or DEFAULT_EXPIRED_MESSAGE,
    )


def store_paged_session(state: dict[str, Any]) -> str:
    return _global_store.put(state)


async def try_handle_pager_component(interaction: dict[str, Any]) -> dict[str, Any] | None:
    custom_id = (interaction.get("data") or {}).get("custom_id") or ""
    parsed = parse_pager_custom_id(custom_id)
    if not parsed:
        return None
    prefix, session_id, nav_token = parsed
    reg = _registrations.get(prefix)
    if not reg:
        return None
    state = _global_store.get(session_id)
    if state is None:
        return {"content": reg.expired_message}
    try:
        return await reg.render(state, session_id, nav_token)
    except Exception as e:
        pagination_log.error(
            "PAGER_RENDER_FAILED", e, {"prefix": prefix, "nav_token": nav_token}
        )
        observe_pager_render_failure(prefix)
        return {"content": "Something went wrong updating this page."}
