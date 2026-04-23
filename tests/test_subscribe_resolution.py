from __future__ import annotations

import unittest

from src.commands.subscribe_resolution import parse_clan_group_id


class ParseClanGroupIdTests(unittest.TestCase):
    def test_accepts_numeric_id(self) -> None:
        self.assertEqual(parse_clan_group_id("123456"), "123456")

    def test_parses_raidhub_url(self) -> None:
        self.assertEqual(
            parse_clan_group_id("https://raidhub.io/clan/987654321"),
            "987654321",
        )

    def test_parses_bungie_url_query(self) -> None:
        self.assertEqual(
            parse_clan_group_id(
                "https://www.bungie.net/7/en/Clan/Profile?groupId=42424242"
            ),
            "42424242",
        )

    def test_returns_none_for_unparseable_value(self) -> None:
        self.assertIsNone(parse_clan_group_id("not-a-clan-id"))


if __name__ == "__main__":
    unittest.main()
