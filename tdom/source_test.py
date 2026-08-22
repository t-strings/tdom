import pytest

from .source import LinePosition


@pytest.mark.parametrize(
    ("start", "text", "expected"),
    (
        (LinePosition(2, 3), "", LinePosition(2, 3)),
        (LinePosition(2, 3), "abc", LinePosition(2, 6)),
        (LinePosition(2, 3), "a\nbc", LinePosition(3, 2)),
        (LinePosition(2, 3), "a\n\n", LinePosition(4, 0)),
    ),
)
def test_advance_over(
    start: LinePosition,
    text: str,
    expected: LinePosition,
) -> None:
    assert start.advance_over(text) == expected
