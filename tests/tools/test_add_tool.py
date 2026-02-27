from __future__ import annotations

import pytest

from src.tools.add_tool import add


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (1, 1, 2),
        (2, 3, 5),
        (0, 0, 0),
        (-1, 1, 0),
        (-10, -5, -15),
        (999, 1, 1000),
        (2_000_000, 3_000_000, 5_000_000),
        (-2_000_000, 3_000_000, 1_000_000),
        (42, -42, 0),
        (7, 8, 15),
    ],
)
def test_add_tool_cases(a: int, b: int, expected: int) -> None:
    assert add.invoke({"a": a, "b": b}) == expected
