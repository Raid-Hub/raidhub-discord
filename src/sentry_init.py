from __future__ import annotations

import sentry_sdk

from .config import Settings
from .log import ingress


def init_sentry(settings: Settings) -> None:
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        ingress.info("SENTRY_DISABLED", {})
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.sentry_environment or "development",
        release=settings.sentry_release or None,
        # FastAPI integration auto-enables when fastapi is installed.
        send_default_pii=settings.sentry_send_default_pii,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    ingress.info(
        "SENTRY_ENABLED",
        {
            "environment": settings.sentry_environment or "development",
            "has_release": bool(settings.sentry_release),
            "send_default_pii": settings.sentry_send_default_pii,
            "traces_sample_rate": settings.sentry_traces_sample_rate,
        },
    )
