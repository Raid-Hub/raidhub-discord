from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscription_messages import (
    SUBSCRIPTION_COMMAND_TITLE,
    SUBSCRIPTION_REQUEST_FAILED_TITLE,
)
from .subscription_helpers import (
    format_subscription_status_embed,
    subscription_envelope_error_message,
)
from .subscription_routes import SUB_ROUTE_STATUS, SUBSCRIPTION_WEBHOOKS_PATH
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    error_embed,
    patch_discord_followup_best_effort,
    report_deferred_exception,
    require_manage_webhooks_or_warn,
    warn_embed,
)


async def run_subscription_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        data = interaction.get("data") or {}
        top_opts = data.get("options") or []
        sub = "status"
        if top_opts and isinstance(top_opts[0], dict):
            sub = str(top_opts[0].get("name") or "").strip().lower() or "status"
        if sub != "status":
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(SUBSCRIPTION_COMMAND_TITLE, "Use `/subscriptions` to view status."),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    SUBSCRIPTION_COMMAND_TITLE,
                    "Run this command in a server channel, not a DM.",
                ),
            )
            return

        if not await require_manage_webhooks_or_warn(
            interaction, app_id=app_id, token=token, title=SUBSCRIPTION_COMMAND_TITLE
        ):
            return

        ctx = discord_invocation_context(interaction, route_id=SUB_ROUTE_STATUS)
        env = await raidhub.request_envelope(
            "GET",
            SUBSCRIPTION_WEBHOOKS_PATH,
            discord_context=ctx,
        )

        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    SUBSCRIPTION_REQUEST_FAILED_TITLE,
                    subscription_envelope_error_message(env),
                ),
            )
            return

        inner = env.get("response") or {}
        msg = await format_subscription_status_embed(raidhub, inner)
        await patch_discord_followup_best_effort(app_id, token, msg)
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="subscriptions",
            log_key="SUBSCRIPTION_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed("Subscription Failed", USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="subscriptions", outcome=outcome)


__all__ = ["run_subscription_deferred"]
