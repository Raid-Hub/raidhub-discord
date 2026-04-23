"""Prometheus metrics for Discord ingress (``POST /interactions`` and deferred follow-ups)."""

from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

INTERACTION_REQUESTS = Counter(
    "raidhub_discord_interaction_requests_total",
    "Discord POST /interactions handled (handler + HTTP-level status).",
    ["handler", "status"],
)

INTERACTION_DURATION = Histogram(
    "raidhub_discord_interaction_duration_seconds",
    "Wall time to produce the HTTP response for POST /interactions.",
    ["handler"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

DEFERRED_COMPLETIONS = Counter(
    "raidhub_discord_deferred_command_completions_total",
    "Deferred slash-command background tasks finished (outcome from task perspective).",
    ["command", "outcome"],
)

PAGER_RENDER_FAILURES = Counter(
    "raidhub_discord_pager_render_failures_total",
    "Registered pager render raised before returning an update payload.",
    ["prefix"],
)


def observe_interaction(*, handler: str, status: str, started_monotonic: float) -> None:
    INTERACTION_REQUESTS.labels(handler=handler, status=status).inc()
    INTERACTION_DURATION.labels(handler=handler).observe(time.perf_counter() - started_monotonic)


def observe_deferred_completion(*, command: str, outcome: str) -> None:
    DEFERRED_COMPLETIONS.labels(command=command, outcome=outcome).inc()


def observe_pager_render_failure(prefix: str) -> None:
    PAGER_RENDER_FAILURES.labels(prefix=prefix).inc()


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
