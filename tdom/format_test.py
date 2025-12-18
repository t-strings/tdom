from string.templatelib import Interpolation

from .format import convert, format_interpolation, format_template


class Convertible:
    def __str__(self) -> str:
        return "Convertible str"

    def __repr__(self) -> str:
        return "Convertible repr"


def test_convert_none():
    value = Convertible()
    assert convert(value, None) is value


def test_convert_a():
    value = Convertible()
    assert convert(value, "a") == "Convertible repr"
    assert convert("Café", "a") == "'Caf\\xe9'"


def test_convert_r():
    value = Convertible()
    assert convert(value, "r") == "Convertible repr"


def test_convert_s():
    value = Convertible()
    assert convert(value, "s") == "Convertible str"


def test_format_interpolation_no_formatting():
    value = Convertible()
    interp = Interpolation(value, expression="", conversion=None, format_spec="")
    assert format_interpolation(interp) is value


def test_format_interpolation_a():
    value = Convertible()
    interp = Interpolation(value, expression="", conversion="a", format_spec="")
    assert format_interpolation(interp) == "Convertible repr"


def test_format_interpolation_r():
    value = Convertible()
    interp = Interpolation(value, expression="", conversion="r", format_spec="")
    assert format_interpolation(interp) == "Convertible repr"


def test_format_interpolation_s():
    value = Convertible()
    interp = Interpolation(value, expression="", conversion="s", format_spec="")
    assert format_interpolation(interp) == "Convertible str"


def test_format_interpolation_default_formatting():
    value = 42
    interp = Interpolation(value, expression="", conversion=None, format_spec="5d")
    assert format_interpolation(interp) == "   42"


def test_format_interpolation_custom_formatter_match_exact():
    value = 42
    interp = Interpolation(value, expression="", conversion=None, format_spec="custom")

    def formatter(val: object, spec: str) -> str:
        return f"formatted-{val}-{spec}"

    assert (
        format_interpolation(interp, formatters=[("custom", formatter)])
        == "formatted-42-custom"
    )


def test_format_interpolation_custom_formatter_match_predicate():
    value = 42
    interp = Interpolation(
        value, expression="", conversion=None, format_spec="custom123"
    )

    def matcher(spec: str) -> bool:
        return spec.startswith("custom")

    def formatter(val: object, spec: str) -> str:
        return f"formatted-{val}-{spec}"

    assert (
        format_interpolation(interp, formatters=[(matcher, formatter)])
        == "formatted-42-custom123"
    )


def test_format_template():
    t = t"Value: {42.19:.1f}, Text: {Convertible()!s}, Raw: {Convertible()!r}"
    result = format_template(t)
    assert result == "Value: 42.2, Text: Convertible str, Raw: Convertible repr"
