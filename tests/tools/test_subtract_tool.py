from __future__ import annotations

import pytest

from src.tools.mathematical_operations.subtract_tool import subtract


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (1, 1, 0),
        (10, 3, 7),
        (0, 0, 0),
        (-1, 1, -2),
        (-10, -5, -5),
        (999, 1, 998),
        (2_000_000, 3_000_000, -1_000_000),
        (-2_000_000, 3_000_000, -5_000_000),
        (42, -42, 84),
        (7, 8, -1),
    ],
)
def test_subtract_tool_cases(a: int, b: int, expected: int) -> None:
    assert subtract.invoke({"a": a, "b": b}) == expected
