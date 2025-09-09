import pytest

from .classnames import classnames


def test_classnames_empty():
    assert classnames() == ""


def test_classnames_strings():
    assert classnames("btn", "btn-primary") == "btn btn-primary"


def test_classnames_strings_strip():
    assert classnames("  btn  ", " btn-primary ") == "btn btn-primary"


def test_cslx_empty_strings():
    assert classnames("", "btn", "", "btn-primary", "") == "btn btn-primary"


def test_clsx_booleans():
    assert classnames(True, False) == ""


def test_classnames_lists_and_tuples():
    assert (
        classnames(["btn", "btn-primary"], ("active", "disabled"))
        == "btn btn-primary active disabled"
    )


def test_classnames_dicts():
    assert (
        classnames(
            "btn",
            {"btn-primary": True, "disabled": False, "active": True, "shown": "yes"},
        )
        == "btn btn-primary active shown"
    )


def test_classnames_mixed_inputs():
    assert (
        classnames(
            "btn",
            ["btn-primary", "active"],
            {"disabled": True, "hidden": False},
            ("extra",),
        )
        == "btn btn-primary active disabled extra"
    )


def test_classnames_ignores_none_and_false():
    assert (
        classnames("btn", None, False, "active", {"hidden": None, "visible": True})
        == "btn active visible"
    )


def test_classnames_raises_type_error_on_invalid_input():
    with pytest.raises(ValueError):
        classnames(123)

    with pytest.raises(ValueError):
        classnames(["btn", 456])


def test_classnames_kitchen_sink():
    assert (
        classnames(
            "foo",
            [1 and "bar", {"baz": False, "bat": None}, ["hello", ["world"]]],
            "cya",
        )
        == "foo bar hello world cya"
    )
