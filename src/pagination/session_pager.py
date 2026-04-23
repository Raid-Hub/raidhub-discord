"""
Reusable Discord "pager" sessions + message-component navigation.

Sessions
    Opaque JSON-serializable state keyed by a short id, TTL in memory (single-process).

custom_id contract
    ``{prefix}:{session_id}:{nav_token}``

    ``nav_token`` is **opaque to this module** — only your registered renderer interprets it.
    Examples:

    - **Offset / page index:** ``build_pager_action_row`` uses ``p{target}`` / ``n{target}`` (see
      ``parse_offset_page_nav_token``); initial slash render and a **Start** control may use plain
      ``"0"`` for page 0.
    - **Cursor-style:** ``"prev"`` / ``"next"`` (renderer reads cursors from ``state``); or a
      short opaque key that maps to a cursor stored server-side in ``state``.

    Use ``str.split(":", 2)`` so ``nav_token`` may contain ``:`` if you ever need it (keep total
    ``custom_id`` length ≤ 100 per Discord limits).

Register ``prefix`` with ``async render(state, session_id, nav_token) ->`` Discord message body.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..discord_v10_enums import ButtonStyle, ComponentType
from ..log import pagination as pagination_log
from ..prom_metrics import observe_pager_render_failure

DEFAULT_SESSION_TTL_SEC = 600.0
DEFAULT_EXPIRED_MESSAGE = "This session expired. Run the command again."

PagerRenderFn = Callable[[dict[str, Any], str, str], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class _PagerRegistration:
    render: PagerRenderFn
    expired_message: str


class InMemoryPagedSessionStore:
    """TTL map ``session_id -> opaque state`` (single-process; not for multi-worker)."""

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
    """
    Register a component handler for ``prefix``.

    ``render(state, session_id, nav_token)`` (async) returns the full Discord message update body
    (``content``, ``embeds``, ``components``, …). Interpret ``nav_token`` however fits the
    feature (integer page, ``next``/``prev``, encoded cursor, …).
    """
    if ":" in prefix:
        raise ValueError("pager prefix must not contain ':'")
    _registrations[prefix] = _PagerRegistration(
        render=render,
        expired_message=expired_message or DEFAULT_EXPIRED_MESSAGE,
    )


def store_paged_session(state: dict[str, Any]) -> str:
    """Persist state for any registered pager; returns ``session_id`` for custom_ids."""
    return _global_store.put(state)


def clamp_page(page: int, total_pages: int) -> int:
    """Clamp 0-based page index (offset UIs)."""
    if total_pages < 1:
        return 0
    return max(0, min(page, total_pages - 1))


def total_page_count(item_count: int, page_size: int) -> int:
    """Number of 0-indexed pages for ``item_count`` items at ``page_size`` per page (min 1)."""
    if page_size < 1:
        return 1
    return max(1, (max(0, item_count) + page_size - 1) // page_size)


def parse_nav_token_as_int(nav_token: str, *, default: int = 0) -> int:
    """Parse ``nav_token`` as a plain decimal page index."""
    try:
        return int(nav_token.strip(), 10)
    except ValueError:
        return default


def parse_offset_page_nav_token(nav_token: str, *, default: int = 0) -> int:
    """
    Decode page index from ``build_pager_action_row`` tokens ``p{target}`` / ``n{target}``
    (prev vs next so both buttons never share the same ``custom_id`` on a one-page result),
    or a plain decimal for legacy / initial loads.
    """
    t = nav_token.strip()
    if len(t) >= 2 and t[0] in ("p", "n"):
        try:
            return int(t[1:], 10)
        except ValueError:
            return default
    return parse_nav_token_as_int(t, default=default)


def parse_pager_custom_id(custom_id: str) -> tuple[str, str, str] | None:
    """
    Parse ``prefix:session_id:nav_token``.

    ``nav_token`` is returned verbatim (may be empty string — renderers should treat as invalid).
    """
    parts = custom_id.split(":", 2)
    if len(parts) != 3:
        return None
    prefix, session_id, nav_token = parts[0], parts[1], parts[2]
    if not prefix or not session_id:
        return None
    return prefix, session_id, nav_token


def pager_custom_id(prefix: str, session_id: str, nav_token: str) -> str:
    return f"{prefix}:{session_id}:{nav_token}"


def build_dual_nav_action_row(
    *,
    prefix: str,
    session_id: str,
    prev_nav_token: str,
    next_nav_token: str,
    prev_disabled: bool,
    next_disabled: bool,
    prev_label: str = "Prev",
    next_label: str = "Next",
) -> dict[str, Any]:
    """
    Prev/Next buttons with arbitrary ``nav_token`` strings (cursor flows, named actions, …).

    Keep tokens short so ``custom_id`` stays within Discord's 100-character limit.
    """
    return {
        "type": int(ComponentType.ACTION_ROW),
        "components": [
            {
                "type": int(ComponentType.BUTTON),
                "style": int(ButtonStyle.SECONDARY),
                "custom_id": pager_custom_id(prefix, session_id, prev_nav_token),
                "label": prev_label,
                "disabled": prev_disabled,
            },
            {
                "type": int(ComponentType.BUTTON),
                "style": int(ButtonStyle.SECONDARY),
                "custom_id": pager_custom_id(prefix, session_id, next_nav_token),
                "label": next_label,
                "disabled": next_disabled,
            },
        ],
    }


def build_triple_nav_action_row(
    *,
    prefix: str,
    session_id: str,
    first_nav_token: str,
    prev_nav_token: str,
    next_nav_token: str,
    first_disabled: bool,
    prev_disabled: bool,
    next_disabled: bool,
    first_label: str = "Start",
    prev_label: str = "Prev",
    next_label: str = "Next",
) -> dict[str, Any]:
    """Start (first page) / Prev / Next in one row (e.g. ``first_nav_token`` ``\"0\"`` for page 0)."""
    return {
        "type": int(ComponentType.ACTION_ROW),
        "components": [
            {
                "type": int(ComponentType.BUTTON),
                "style": int(ButtonStyle.SECONDARY),
                "custom_id": pager_custom_id(prefix, session_id, first_nav_token),
                "label": first_label,
                "disabled": first_disabled,
            },
            {
                "type": int(ComponentType.BUTTON),
                "style": int(ButtonStyle.SECONDARY),
                "custom_id": pager_custom_id(prefix, session_id, prev_nav_token),
                "label": prev_label,
                "disabled": prev_disabled,
            },
            {
                "type": int(ComponentType.BUTTON),
                "style": int(ButtonStyle.SECONDARY),
                "custom_id": pager_custom_id(prefix, session_id, next_nav_token),
                "label": next_label,
                "disabled": next_disabled,
            },
        ],
    }


def build_pager_action_row(
    *,
    prefix: str,
    session_id: str,
    current_page: int,
    total_pages: int,
    prev_label: str = "Prev",
    next_label: str = "Next",
) -> dict[str, Any]:
    """
    Offset pagination: prev encodes target ``current_page - 1`` as ``p{int}``, next as ``n{int}``
    (always distinct ``custom_id`` values, including single-page results). Decode with
    ``parse_offset_page_nav_token``.

    For cursor-based APIs, use ``build_dual_nav_action_row`` and interpret tokens in your renderer.
    """
    prev_token = f"p{current_page - 1}"
    next_token = f"n{current_page + 1}"
    return build_dual_nav_action_row(
        prefix=prefix,
        session_id=session_id,
        prev_nav_token=prev_token,
        next_nav_token=next_token,
        prev_disabled=current_page <= 0,
        next_disabled=current_page >= total_pages - 1,
        prev_label=prev_label,
        next_label=next_label,
    )


async def try_handle_pager_component(interaction: dict[str, Any]) -> dict[str, Any] | None:
    """
    If ``data.custom_id`` matches a registered pager, return the new message payload
    (for ``UPDATE_MESSAGE``). Otherwise return ``None``.
    """
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
