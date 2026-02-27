from __future__ import annotations

import pytest

from src.tools.mathematical_operations.multiply_tool import multiply


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (1, 1, 1),
        (2, 3, 6),
        (0, 0, 0),
        (-1, 1, -1),
        (-10, -5, 50),
        (999, 1, 999),
        (2_000_000, 3, 6_000_000),
        (-2_000_000, 3, -6_000_000),
        (42, -42, -1764),
        (7, 8, 56),
    ],
)
def test_multiply_tool_cases(a: int, b: int, expected: int) -> None:
    assert multiply.invoke({"a": a, "b": b}) == expected
