from __future__ import annotations

from typing import Any

from ..config import Settings
from ..pagination import store_paged_session
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient
from .player_search_helpers import (
    PLAYER_SEARCH_PAGE_SIZE,
    player_search_render_from_state,
    register_player_search_pager,
)
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    flatten_options,
    patch_discord_followup_best_effort,
    report_deferred_exception,
)


async def run_player_search_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        opts = flatten_options(interaction.get("data", {}).get("options"))
        query = str(opts.get("search_query") or opts.get("query") or "").strip()
        if not query:
            await patch_discord_followup_best_effort(
                app_id, token, {"content": "Provide a **search_query** option to search."}
            )
            return

        query_params: dict[str, Any] = {"query": query}

        page_size = PLAYER_SEARCH_PAGE_SIZE
        session_id = store_paged_session(
            {"query_params": query_params, "page_size": page_size}
        )
        payload = await player_search_render_from_state(
            raidhub,
            {"query_params": query_params, "page_size": page_size},
            session_id,
            "0",
        )
        await patch_discord_followup_best_effort(app_id, token, payload)
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="player-search",
            log_key="PLAYER_SEARCH_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload={"content": USER_FACING_GENERIC},
        )
    finally:
        observe_deferred_completion(command="player-search", outcome=outcome)


__all__ = ["register_player_search_pager", "run_player_search_deferred"]
