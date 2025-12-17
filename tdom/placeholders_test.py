import pytest

from .placeholders import (
    _PLACEHOLDER_PREFIX,
    _PLACEHOLDER_SUFFIX,
    PlaceholderState,
    find_placeholders,
    make_placeholder,
    match_placeholders,
)


def test_make_placeholder() -> None:
    assert make_placeholder(0) == f"{_PLACEHOLDER_PREFIX}0{_PLACEHOLDER_SUFFIX}"
    assert make_placeholder(42) == f"{_PLACEHOLDER_PREFIX}42{_PLACEHOLDER_SUFFIX}"


def test_match_placeholders() -> None:
    s = f"Start {_PLACEHOLDER_PREFIX}0{_PLACEHOLDER_SUFFIX} middle {_PLACEHOLDER_PREFIX}1{_PLACEHOLDER_SUFFIX} end"
    matches = match_placeholders(s)
    assert len(matches) == 2
    assert matches[0].group(0) == f"{_PLACEHOLDER_PREFIX}0{_PLACEHOLDER_SUFFIX}"
    assert matches[0][1] == "0"
    assert matches[1].group(0) == f"{_PLACEHOLDER_PREFIX}1{_PLACEHOLDER_SUFFIX}"
    assert matches[1][1] == "1"


def test_find_placeholders() -> None:
    s = f"Hello {_PLACEHOLDER_PREFIX}0{_PLACEHOLDER_SUFFIX}, today is {_PLACEHOLDER_PREFIX}1{_PLACEHOLDER_SUFFIX}."
    pt = find_placeholders(s)
    assert pt.strings == ("Hello ", ", today is ", ".")
    assert pt.i_indexes == (0, 1)

    literal_s = "No placeholders here."
    literal_pt = find_placeholders(literal_s)
    assert literal_pt.strings == (literal_s,)
    assert literal_pt.i_indexes == ()


def test_placeholder_state() -> None:
    state = PlaceholderState()
    assert state.is_empty

    p0 = state.add_placeholder(0)
    assert p0 == make_placeholder(0)
    assert not state.is_empty

    p1 = state.add_placeholder(1)
    assert p1 == make_placeholder(1)

    text = f"Values: {p0}, {p1}"
    pt = state.remove_placeholders(text)
    assert pt.strings == ("Values: ", ", ", "")
    assert pt.i_indexes == (0, 1)
    assert state.is_empty

    with pytest.raises(ValueError):
        state.remove_placeholders(f"Unknown placeholder: {make_placeholder(2)}")
