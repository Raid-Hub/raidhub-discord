from __future__ import annotations

import unittest

from src.pagination.ids import pager_custom_id, parse_pager_custom_id
from src.pagination.tokens import (
    parse_nav_token_as_int,
    parse_offset_page_nav_token,
    total_page_count,
)


class PaginationTokensAndIdsTests(unittest.TestCase):
    def test_custom_id_round_trip(self) -> None:
        cid = pager_custom_id("ps", "abc123", "n2")
        self.assertEqual(parse_pager_custom_id(cid), ("ps", "abc123", "n2"))

    def test_parse_custom_id_rejects_bad_shape(self) -> None:
        self.assertIsNone(parse_pager_custom_id("bad"))
        self.assertIsNone(parse_pager_custom_id("::"))

    def test_parse_offset_tokens(self) -> None:
        self.assertEqual(parse_offset_page_nav_token("p3"), 3)
        self.assertEqual(parse_offset_page_nav_token("n4"), 4)
        self.assertEqual(parse_offset_page_nav_token("5"), 5)
        self.assertEqual(parse_offset_page_nav_token("x"), 0)

    def test_parse_nav_token_as_int_default(self) -> None:
        self.assertEqual(parse_nav_token_as_int("7"), 7)
        self.assertEqual(parse_nav_token_as_int("bad", default=2), 2)

    def test_total_page_count(self) -> None:
        self.assertEqual(total_page_count(0, 10), 1)
        self.assertEqual(total_page_count(11, 10), 2)


if __name__ == "__main__":
    unittest.main()
