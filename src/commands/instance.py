from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    discord_message_for_failed_envelope,
    flatten_options,
    patch_discord_followup_best_effort,
    report_deferred_exception,
)


def _format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"


async def run_instance_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        opts = flatten_options(interaction.get("data", {}).get("options"))
        raw_id = opts.get("raid_instance_id") or opts.get("instance_id")
        if raw_id is None or str(raw_id).strip() == "":
            await patch_discord_followup_best_effort(
                app_id, token, {"content": "Provide a **raid_instance_id** to look up."}
            )
            return
        instance_id = str(raw_id).strip()

        env = await raidhub.request_envelope("GET", f"/instance/{instance_id}")
        if not env.get("success"):
            code = str(env.get("code", ""))
            if code == "InstanceNotFoundError":
                await patch_discord_followup_best_effort(
                    app_id, token, {"content": "Instance not found."}
                )
                return
            await patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": discord_message_for_failed_envelope(code, "")},
            )
            return

        inst = env.get("response") or {}
        meta = inst.get("metadata") or {}
        title = str(meta.get("activityName") or "Raid instance")
        desc = f"Instance `{inst.get('instanceId', instance_id)}`"
        date_done = inst.get("dateCompleted")
        date_s = str(date_done) if date_done else "—"
        embed = {
            "title": title,
            "description": desc,
            "color": 0x5865_F2,
            "fields": [
                {
                    "name": "Version",
                    "value": str(meta.get("versionName") or "—"),
                    "inline": True,
                },
                {
                    "name": "Players",
                    "value": str(inst.get("playerCount", "—")),
                    "inline": True,
                },
                {
                    "name": "Duration",
                    "value": _format_duration(int(inst.get("duration") or 0)),
                    "inline": True,
                },
                {
                    "name": "Completed",
                    "value": "Yes" if inst.get("completed") else "No",
                    "inline": True,
                },
                {
                    "name": "Fresh",
                    "value": "Yes" if inst.get("fresh") else "No",
                    "inline": True,
                },
                {
                    "name": "Flawless",
                    "value": "Yes" if inst.get("flawless") else "No",
                    "inline": True,
                },
                {"name": "Completed At", "value": date_s, "inline": False},
            ],
        }
        await patch_discord_followup_best_effort(app_id, token, {"embeds": [embed]})
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="instance",
            log_key="INSTANCE_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload={"content": USER_FACING_GENERIC},
        )
    finally:
        observe_deferred_completion(command="instance", outcome=outcome)


__all__ = ["run_instance_deferred"]
