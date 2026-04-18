from __future__ import annotations

import pytest

from scotty.ui.output import display_width


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("Task", 4),
        ("Run migrations", 14),
        ("🏁", 2),
        ("✨", 2),
        ("📦", 2),
        ("🗄️", 2),  # emoji with variation selector (2 codepoints, 2 cols)
        ("🏁  Start deployment", 20),
        ("🗄️  Run migrations", 18),
    ],
)
def test_display_width(text, expected):
    assert display_width(text) == expected


def test_display_width_strips_ansi():
    assert display_width("\033[32mhello\033[0m") == 5
