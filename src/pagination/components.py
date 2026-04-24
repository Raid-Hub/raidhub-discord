from __future__ import annotations

from typing import Any

from ..discord_v10_enums import ButtonStyle, ComponentType
from .ids import pager_custom_id


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
