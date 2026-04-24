from __future__ import annotations

SUBSCRIBE_COMMAND_TITLE = "Subscribe Command"
SUBSCRIBE_FAILED_TITLE = "Subscribe Failed"
SUBSCRIPTION_COMMAND_TITLE = "Subscription Command"
SUBSCRIPTION_REQUEST_FAILED_TITLE = "Subscription Request Failed"
UNSUBSCRIBE_COMMAND_TITLE = "Unsubscribe Command"
UNSUBSCRIBE_FAILED_TITLE = "Unsubscribe Failed"
UNSUBSCRIBE_PLAYER_TITLE = "Unsubscribe Player"
UNSUBSCRIBE_CLAN_TITLE = "Unsubscribe Clan"
PLAYER_NOT_FOUND_TITLE = "Player Not Found"
CLAN_ID_NOT_RECOGNIZED_TITLE = "Clan ID Not Recognized"
SUBSCRIPTION_SAVED_TITLE = "Subscription Saved"
SUBSCRIPTION_REMOVED_TITLE = "Subscription Removed"
PLAYER_UNSUBSCRIBED_TITLE = "Player Unsubscribed"
CLAN_UNSUBSCRIBED_TITLE = "Clan Unsubscribed"
SUBSCRIPTION_STATUS_RULES_HINT = (
    "Use `/subscription status` to see all rules for this channel."
)


def subscribe_success_description(display_label: str, resolved_id: str, channel_id: str) -> str:
    return (
        f"Subscribed to **{display_label}** (`{resolved_id}`) in <#{channel_id}>. "
        f"{SUBSCRIPTION_STATUS_RULES_HINT}"
    )


def unsubscribe_success_description(display_label: str, resolved_id: str) -> str:
    return (
        f"Removed **{display_label}** (`{resolved_id}`) from this channel. Other subscription "
        "rules are unchanged."
    )
