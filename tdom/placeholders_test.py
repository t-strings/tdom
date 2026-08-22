import pytest

from .placeholders import (
    PlaceholderState,
    make_placeholder_config,
)


def test_make_placeholder() -> None:
    config = make_placeholder_config()
    assert config.make_placeholder(0) == f"{config.prefix}0{config.suffix}"
    assert config.make_placeholder(42) == f"{config.prefix}42{config.suffix}"


def test_match_placeholders() -> None:
    config = make_placeholder_config()
    s = f"Start {config.prefix}0{config.suffix} middle {config.prefix}1{config.suffix} end"
    matches = config.match_placeholders(s)
    assert len(matches) == 2
    assert matches[0].group(0) == f"{config.prefix}0{config.suffix}"
    assert matches[0][1] == "0"
    assert matches[1].group(0) == f"{config.prefix}1{config.suffix}"
    assert matches[1][1] == "1"


def test_find_placeholders() -> None:
    config = make_placeholder_config()
    s = f"Hello {config.prefix}0{config.suffix}, today is {config.prefix}1{config.suffix}."
    pt = config.find_placeholders(s)
    assert pt.strings == ("Hello ", ", today is ", ".")
    assert (pt.i_start, pt.i_stop) == (0, 2)

    literal_s = "No placeholders here."
    literal_pt = config.find_placeholders(literal_s)
    assert literal_pt.strings == (literal_s,)
    assert literal_pt.i_count == 0


def test_find_placeholders_rejects_discontiguous_indexes() -> None:
    config = make_placeholder_config()
    text = f"{config.make_placeholder(1)}{config.make_placeholder(3)}"

    with pytest.raises(ValueError, match="indexes must be contiguous"):
        _ = config.find_placeholders(text)


def test_placeholder_state() -> None:
    config = make_placeholder_config()
    state = PlaceholderState(config=config)
    assert state.is_empty

    p0 = state.add_placeholder(0)
    assert p0 == config.make_placeholder(0)
    assert not state.is_empty

    p1 = state.add_placeholder(1)
    assert p1 == config.make_placeholder(1)

    text = f"Values: {p0}, {p1}"
    pt = state.remove_placeholders(text)
    assert pt.strings == ("Values: ", ", ", "")
    assert (pt.i_start, pt.i_stop) == (0, 2)
    assert state.is_empty

    with pytest.raises(ValueError):
        state.remove_placeholders(f"Unknown placeholder: {config.make_placeholder(2)}")
