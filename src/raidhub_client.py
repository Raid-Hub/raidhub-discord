from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import httpx
import jwt

from .log import raidhub_api

DISCORD_AUTH_SCHEME = "Discord"


class RaidHubEnvelopeCode(StrEnum):
    RAIDHUB_API_UNREACHABLE = "RaidHubApiUnreachable"
    NON_JSON_RESPONSE = "NonJsonResponse"
    RAIDHUB_API_SERVER_ERROR = "RaidHubApiServerError"
    RAIDHUB_API_CLIENT_ERROR = "RaidHubApiClientError"


def discord_invocation_context(
    interaction: dict[str, Any],
    *,
    route_id: str,
) -> dict[str, Any]:
    """
    Payload for ``Authorization: Discord <jwt>`` (matches RaidHub API
    ``zDiscordInvocationContext``).
    """
    member = interaction.get("member") or {}
    user = member.get("user") if isinstance(member, dict) else None
    if not user:
        user = interaction.get("user") or {}
    data = interaction.get("data") or {}
    payload: dict[str, Any] = {
        "interactionId": str(interaction.get("id") or ""),
        "commandName": str(data.get("name") or ""),
        "userId": str((user or {}).get("id") or ""),
        "routeId": route_id,
    }
    gid = interaction.get("guild_id")
    cid = interaction.get("channel_id")
    if gid is not None:
        payload["guildId"] = str(gid)
    if cid is not None:
        payload["channelId"] = str(cid)
    return payload


class RaidHubClient:
    def __init__(self, base_url: str, jwt_secret: str, *, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._jwt_secret = jwt_secret
        self._api_key = api_key

    def _sign_discord_jwt(self, discord_context: dict[str, Any]) -> str:
        now = datetime.now(tz=timezone.utc)
        payload = {
            **discord_context,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=120)).timestamp()),
        }
        return jwt.encode(payload, self._jwt_secret, algorithm="HS256")

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        discord_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        if discord_context:
            headers["authorization"] = (
                f"{DISCORD_AUTH_SCHEME} {self._sign_discord_jwt(discord_context)}"
            )
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15) as client:
            response = await client.request(method, path, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    async def request_envelope(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        discord_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Normalize RaidHub JSON envelopes and HTTP status without raising on transport/HTTP errors."""
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        if discord_context:
            headers["authorization"] = (
                f"{DISCORD_AUTH_SCHEME} {self._sign_discord_jwt(discord_context)}"
            )
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=30) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers=headers,
                )
        except httpx.RequestError as e:
            raidhub_api.warn(
                "RAIDHUB_API_REQUEST_FAILED",
                e,
                {"base_url": self._base_url, "method": method, "path": path},
            )
            return {
                "success": False,
                "code": RaidHubEnvelopeCode.RAIDHUB_API_UNREACHABLE.value,
                "error": {
                    "message": str(e),
                    "base_url": self._base_url,
                    "method": method,
                    "path": path,
                },
            }

        try:
            data: Any = response.json()
        except Exception:
            data = None

        status = response.status_code
        if 200 <= status < 300:
            if isinstance(data, dict):
                return data
            return {
                "success": False,
                "code": RaidHubEnvelopeCode.NON_JSON_RESPONSE.value,
                "error": {"message": response.text[:500], "httpStatus": status},
            }

        if status >= 500:
            return {
                "success": False,
                "code": RaidHubEnvelopeCode.RAIDHUB_API_SERVER_ERROR.value,
                "error": {"httpStatus": status},
            }

        if isinstance(data, dict) and data.get("success") is False:
            return data

        return {
            "success": False,
            "code": RaidHubEnvelopeCode.RAIDHUB_API_CLIENT_ERROR.value,
            "error": {"httpStatus": status},
        }
