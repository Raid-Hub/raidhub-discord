from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscription_helpers import (
    SUB_ROUTE_DELETE,
    SUB_ROUTE_PUT,
    SUB_ROUTE_STATUS,
    build_subscription_json_body,
    format_subscription_status_embed,
    subscription_envelope_error_message,
    subscription_rules_suffix,
)
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    error_embed,
    flatten_options,
    patch_discord_followup_best_effort,
    report_deferred_exception,
    success_embed,
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
        if not top_opts or not isinstance(top_opts[0], dict):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Subscription Command",
                    "Pick `register`, `update`, `delete`, or `status` under `/subscription`.",
                ),
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("register", "update", "delete", "status"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed("Subscription Command", "Unknown `/subscription` subcommand."),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Subscription Command",
                    "Run this command in a server channel, not a DM.",
                ),
            )
            return

        leaf_opts = flatten_options(top_opts[0].get("options"))
        route_id = {
            "register": SUB_ROUTE_PUT,
            "update": SUB_ROUTE_PUT,
            "delete": SUB_ROUTE_DELETE,
            "status": SUB_ROUTE_STATUS,
        }[sub]
        ctx = discord_invocation_context(interaction, route_id=route_id)

        if sub == "status":
            env = await raidhub.request_envelope(
                "GET",
                "/subscriptions/discord/webhooks",
                discord_context=ctx,
            )
        elif sub == "delete":
            env = await raidhub.request_envelope(
                "DELETE",
                "/subscriptions/discord/webhooks",
                discord_context=ctx,
            )
        else:
            payload = build_subscription_json_body(leaf_opts)
            env = await raidhub.request_envelope(
                "PUT",
                "/subscriptions/discord/webhooks",
                json=payload if payload else {},
                discord_context=ctx,
            )

        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    "Subscription Request Failed",
                    subscription_envelope_error_message(env),
                ),
            )
            return

        inner = env.get("response") or {}
        if sub == "status":
            msg = format_subscription_status_embed(inner)
        elif sub == "delete":
            msg = success_embed(
                "Subscription Removed",
                "RaidHub will no longer use a webhook in this channel.",
            )
        elif sub == "register":
            parts = [
                "RaidHub subscription events will post to this channel.",
            ]
            if inner.get("created"):
                parts.append("A new subscription destination was created.")
            if inner.get("activated"):
                parts.append("The destination was re-activated.")
            rules = inner.get("rules") or {}
            rs = subscription_rules_suffix(rules)
            if rs:
                parts.append(rs)
            msg = success_embed("Subscription Registered", " ".join(parts))
        else:
            parts = ["Subscription rules for this channel were saved."]
            if inner.get("activated"):
                parts.append("The destination was re-activated.")
            rules = inner.get("rules") or {}
            rs = subscription_rules_suffix(rules)
            if rs:
                parts.append(rs)
            msg = success_embed("Subscription Updated", " ".join(parts))

        await patch_discord_followup_best_effort(app_id, token, msg)
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="subscription",
            log_key="SUBSCRIPTION_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed("Subscription Failed", USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="subscription", outcome=outcome)


__all__ = ["run_subscription_deferred"]
