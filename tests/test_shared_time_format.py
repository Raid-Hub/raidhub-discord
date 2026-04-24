from __future__ import annotations

import unittest

from src.commands.shared import iso_to_discord_relative


class IsoToDiscordRelativeTests(unittest.TestCase):
    def test_returns_dash_for_empty_like_values(self) -> None:
        self.assertEqual(iso_to_discord_relative(None), "—")
        self.assertEqual(iso_to_discord_relative(""), "—")
        self.assertEqual(iso_to_discord_relative("   "), "—")

    def test_returns_dash_for_invalid_iso(self) -> None:
        self.assertEqual(iso_to_discord_relative("not-an-iso"), "—")

    def test_formats_valid_utc_iso(self) -> None:
        out = iso_to_discord_relative("2026-04-23T03:20:43Z")
        self.assertTrue(out.startswith("<t:"))
        self.assertTrue(out.endswith(":R>"))


if __name__ == "__main__":
    unittest.main()
