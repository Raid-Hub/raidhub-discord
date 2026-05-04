"""RaidHub API routes for Discord subscription webhooks (under ``/internal``)."""

# HTTP path (leading slash), passed to ``RaidHubClient.request(..., path=...)``.
SUBSCRIPTION_WEBHOOKS_PATH = "/internal/subscriptions/discord/webhooks"

# route_id for Discord invocation JWT (METHOD + path without leading slash).
SUB_ROUTE_PUT = "PUT internal/subscriptions/discord/webhooks"
SUB_ROUTE_DELETE = "DELETE internal/subscriptions/discord/webhooks"
SUB_ROUTE_STATUS = "GET internal/subscriptions/discord/webhooks"
