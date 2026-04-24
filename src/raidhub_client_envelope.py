from __future__ import annotations

from typing import Any

from .log import raidhub_api
from .raidhub_client_types import RaidHubEnvelopeCode


def normalize_envelope_response(
    *,
    base_url: str,
    method: str,
    path: str,
    status: int,
    response_text: str,
    data: Any,
) -> dict[str, Any]:
    if 200 <= status < 300:
        if isinstance(data, dict):
            return data
        raidhub_api.warn(
            "RAIDHUB_API_NON_JSON_SUCCESS",
            None,
            {
                "base_url": base_url,
                "method": method,
                "path": path,
                "http_status": status,
                "body_preview": response_text[:200],
            },
        )
        return {
            "success": False,
            "code": RaidHubEnvelopeCode.NON_JSON_RESPONSE.value,
            "error": {"message": response_text[:500], "httpStatus": status},
        }

    if status >= 500:
        raidhub_api.warn(
            "RAIDHUB_API_SERVER_ERROR_RESPONSE",
            None,
            {
                "base_url": base_url,
                "method": method,
                "path": path,
                "http_status": status,
            },
        )
        return {
            "success": False,
            "code": RaidHubEnvelopeCode.RAIDHUB_API_SERVER_ERROR.value,
            "error": {"httpStatus": status},
        }

    if isinstance(data, dict) and data.get("success") is False:
        err = data.get("error") or {}
        raidhub_api.warn(
            "RAIDHUB_API_ENVELOPE_FAILED",
            None,
            {
                "base_url": base_url,
                "method": method,
                "path": path,
                "http_status": status,
                "code": str(data.get("code") or ""),
                "error_code": str(err.get("code") or ""),
                "error_message": str(err.get("message") or "")[:200],
            },
        )
        return data

    raidhub_api.warn(
        "RAIDHUB_API_CLIENT_ERROR_RESPONSE",
        None,
        {
            "base_url": base_url,
            "method": method,
            "path": path,
            "http_status": status,
            "body_preview": response_text[:200],
        },
    )
    return {
        "success": False,
        "code": RaidHubEnvelopeCode.RAIDHUB_API_CLIENT_ERROR.value,
        "error": {"httpStatus": status},
    }
