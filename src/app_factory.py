from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from discord_interactions import InteractionResponseType, InteractionType
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from .commands import (
    register_player_search_pager,
    run_instance_deferred,
    run_player_search_deferred,
    run_subscribe_deferred,
    run_subscription_deferred,
    run_unsubscribe_clan_deferred,
    run_unsubscribe_deferred,
    run_unsubscribe_player_deferred,
)
from .config import Settings, get_settings
from .discord_auth import verify_discord_signature_with_reason
from .log import ingress
from .pagination import try_handle_pager_component
from .prom_metrics import metrics_response, observe_interaction
from .raidhub_client import RaidHubClient
from .sentry_init import init_sentry

CommandHandler = Callable[[dict[str, Any], RaidHubClient, Settings], Awaitable[None]]


def create_app() -> FastAPI:
    settings = get_settings()
    init_sentry(settings)

    raidhub = RaidHubClient(
        settings.raidhub_api_base_url,
        settings.raidhub_jwt_secret,
        api_key=settings.raidhub_api_key,
    )
    register_player_search_pager(raidhub)

    command_handlers: dict[str, CommandHandler] = {
        "instance": run_instance_deferred,
        "player-search": run_player_search_deferred,
        "subscribe": run_subscribe_deferred,
        "subscription": run_subscription_deferred,
        "unsubscribe": run_unsubscribe_deferred,
        "unsubscribe-player": run_unsubscribe_player_deferred,
        "unsubscribe-clan": run_unsubscribe_clan_deferred,
    }

    def _msg(content: str) -> dict[str, Any]:
        return {
            "type": InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            "data": {"content": content},
        }

    def _validate_startup_settings() -> None:
        if not settings.discord_public_key:
            ingress.warn(
                "DISCORD_PUBLIC_KEY_NOT_CONFIGURED",
                None,
                {"env_key": "DISCORD_PUBLIC_KEY"},
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _validate_startup_settings()
        yield

    app = FastAPI(title="raidhub-discord", lifespan=lifespan)

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        return metrics_response()

    @app.post("/interactions")
    async def discord_interactions(
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> JSONResponse:
        t0 = time.perf_counter()
        signature = request.headers.get("X-Signature-Ed25519", "")
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        raw_body = await request.body()
        signature_ok, signature_reason = verify_discord_signature_with_reason(
            settings.discord_public_key, timestamp, raw_body, signature
        )

        ingress.info(
            "DISCORD_INTERACTION_RECEIVED",
            {
                "path": str(request.url.path),
                "remote_ip": request.client.host if request.client else None,
                "has_signature": bool(signature),
                "has_timestamp": bool(timestamp),
                "has_public_key": bool(settings.discord_public_key),
                "signature_valid": signature_ok,
                "signature_reason": signature_reason,
                "signature_len": len(signature.strip()),
                "timestamp_len": len(timestamp.strip()),
                "body_len": len(raw_body),
            },
        )

        if not signature_ok:
            ingress.warn(
                "DISCORD_SIGNATURE_INVALID",
                None,
                {
                    "reason": signature_reason,
                    "signature_len": len(signature.strip()),
                    "timestamp_len": len(timestamp.strip()),
                    "body_len": len(raw_body),
                },
            )
            observe_interaction(
                handler="signature_invalid", status="rejected", started_monotonic=t0
            )
            raise HTTPException(status_code=401, detail="Invalid Discord signature")

        try:
            interaction = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            ingress.warn(
                "DISCORD_INTERACTION_INVALID_JSON",
                None,
                {"body_len": len(raw_body)},
            )
            observe_interaction(
                handler="invalid_json", status="rejected", started_monotonic=t0
            )
            return JSONResponse(_msg("Invalid interaction payload."), status_code=400)
        interaction_type = interaction.get("type")
        ingress.info("DISCORD_INTERACTION_TYPE", {"type": interaction_type})

        if interaction_type == InteractionType.PING:
            ingress.info("DISCORD_PING_RECEIVED", {})
            observe_interaction(handler="ping", status="ok", started_monotonic=t0)
            return JSONResponse({"type": InteractionResponseType.PONG})

        if interaction_type == InteractionType.MESSAGE_COMPONENT:
            updated = await try_handle_pager_component(interaction)
            if not updated:
                ingress.warn("DISCORD_COMPONENT_UNSUPPORTED", None, {})
                observe_interaction(
                    handler="message_component_unsupported",
                    status="ok",
                    started_monotonic=t0,
                )
                return JSONResponse(
                    {
                        "type": InteractionResponseType.UPDATE_MESSAGE,
                        "data": {"content": "Unsupported interaction component."},
                    }
                )
            observe_interaction(
                handler="message_component_pager",
                status="ok",
                started_monotonic=t0,
            )
            return JSONResponse(
                {"type": InteractionResponseType.UPDATE_MESSAGE, "data": updated}
            )

        if interaction_type != InteractionType.APPLICATION_COMMAND:
            ingress.warn("DISCORD_INTERACTION_UNSUPPORTED", None, {"type": interaction_type})
            observe_interaction(
                handler="application_command_unsupported_type",
                status="ok",
                started_monotonic=t0,
            )
            return JSONResponse(_msg("Unsupported interaction type."))

        name = interaction.get("data", {}).get("name")
        ingress.info("DISCORD_COMMAND_RECEIVED", {"command_name": name})
        handler = command_handlers.get(name)
        if handler:
            background_tasks.add_task(handler, interaction, raidhub, settings)
            handler_label = str(name).replace("-", "_")
            observe_interaction(
                handler=f"application_command_{handler_label}_deferred",
                status="ok",
                started_monotonic=t0,
            )
            return JSONResponse(
                {"type": InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
            )

        ingress.warn("DISCORD_COMMAND_NOT_ENABLED", None, {"command_name": name})
        observe_interaction(
            handler="application_command_unknown",
            status="ok",
            started_monotonic=t0,
        )
        return JSONResponse(_msg("Command not enabled yet."), status_code=200)

    return app
