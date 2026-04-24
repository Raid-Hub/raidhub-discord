from __future__ import annotations

import unittest

from src.discord_permissions import guild_member_has_manage_webhooks
from src.discord_v10_enums import Permission


class ManageWebhooksGuardTests(unittest.TestCase):
    def test_missing_member_denies(self) -> None:
        self.assertFalse(guild_member_has_manage_webhooks({}))
        self.assertFalse(guild_member_has_manage_webhooks({"member": None}))
        self.assertFalse(guild_member_has_manage_webhooks({"member": {}}))

    def test_missing_permissions_denies(self) -> None:
        self.assertFalse(
            guild_member_has_manage_webhooks({"member": {"permissions": None}})
        )

    def test_manage_webhooks_allows(self) -> None:
        p = int(Permission.MANAGE_WEBHOOKS)
        self.assertTrue(guild_member_has_manage_webhooks({"member": {"permissions": str(p)}}))

    def test_administrator_allows(self) -> None:
        p = int(Permission.ADMINISTRATOR)
        self.assertTrue(guild_member_has_manage_webhooks({"member": {"permissions": str(p)}}))

    def test_zero_denies(self) -> None:
        self.assertFalse(guild_member_has_manage_webhooks({"member": {"permissions": "0"}}))


if __name__ == "__main__":
    unittest.main()
