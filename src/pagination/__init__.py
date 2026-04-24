"""Discord message-component navigation (session + opaque nav_token per click)."""

from .components import (
    build_dual_nav_action_row,
    build_pager_action_row,
    build_triple_nav_action_row,
)
from .ids import (
    pager_custom_id,
    parse_pager_custom_id,
)
from .runtime import (
    InMemoryPagedSessionStore,
    default_expired_session_content,
    register_pager,
    store_paged_session,
    try_handle_pager_component,
)
from .tokens import (
    clamp_page,
    parse_nav_token_as_int,
    parse_offset_page_nav_token,
    total_page_count,
)

__all__ = [
    "InMemoryPagedSessionStore",
    "build_dual_nav_action_row",
    "build_pager_action_row",
    "build_triple_nav_action_row",
    "clamp_page",
    "default_expired_session_content",
    "pager_custom_id",
    "parse_nav_token_as_int",
    "parse_offset_page_nav_token",
    "parse_pager_custom_id",
    "register_pager",
    "store_paged_session",
    "total_page_count",
    "try_handle_pager_component",
]
