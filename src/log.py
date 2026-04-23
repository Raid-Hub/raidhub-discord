"""
Subsystem loggers (distinct ``Logger`` prefixes, Go-style).

Import the logger that matches the code’s responsibility; do not construct ``Logger`` elsewhere.
"""

from __future__ import annotations

from .structured_logger import Logger

# Incoming Discord HTTP (FastAPI ``/interactions``)
ingress = Logger("DISCORD_INGRESS")

# Outbound HTTP to RaidHub API
raidhub_api = Logger("RAIDHUB_API_CLIENT")

# Message-component pager (sessions + ``try_handle_pager_component``)
pagination = Logger("DISCORD_PAGER")

# Slash deferred work + Discord PATCH follow-ups to ``@original``
handlers = Logger("DISCORD_HANDLERS")
