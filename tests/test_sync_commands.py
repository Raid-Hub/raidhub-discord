from __future__ import annotations

import unittest

from src.sync_commands import _extract_raid_filter_choices


class SyncCommandsTests(unittest.TestCase):
    def test_extract_raid_filter_choices_uses_listed_raid_order(self) -> None:
        out = _extract_raid_filter_choices(
            {
                "listedRaidIds": [9, 1],
                "activityDefinitions": {
                    "1": {"name": "Leviathan", "path": "leviathan"},
                    "9": {"name": "Vault of Glass", "path": "vaultofglass"},
                },
            }
        )
        self.assertEqual(out, [("Vault of Glass", 9), ("Leviathan", 1)])


if __name__ == "__main__":
    unittest.main()
