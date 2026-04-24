from __future__ import annotations


def clamp_page(page: int, total_pages: int) -> int:
    if total_pages < 1:
        return 0
    return max(0, min(page, total_pages - 1))


def total_page_count(item_count: int, page_size: int) -> int:
    if page_size < 1:
        return 1
    return max(1, (max(0, item_count) + page_size - 1) // page_size)


def parse_nav_token_as_int(nav_token: str, *, default: int = 0) -> int:
    try:
        return int(nav_token.strip(), 10)
    except ValueError:
        return default


def parse_offset_page_nav_token(nav_token: str, *, default: int = 0) -> int:
    t = nav_token.strip()
    if len(t) >= 2 and t[0] in ("p", "n"):
        try:
            return int(t[1:], 10)
        except ValueError:
            return default
    return parse_nav_token_as_int(t, default=default)
