import typing as t
from string.templatelib import Interpolation


@t.overload
def convert[T](value: T, conversion: None) -> T: ...


@t.overload
def convert(value: object, conversion: t.Literal["a", "r", "s"]) -> str: ...


def convert[T](value: T, conversion: t.Literal["a", "r", "s"] | None) -> T | str:
    """
    Convert a value according to the given conversion specifier.

    In the future, something like this should probably ship with Python itself.
    """
    if conversion == "a":
        return ascii(value)
    elif conversion == "r":
        return repr(value)
    elif conversion == "s":
        return str(value)
    else:
        return value


type FormatMatcher = t.Callable[[str], bool]
"""A predicate function that returns True if a given format specifier matches its criteria."""

type CustomFormatter = t.Callable[[object, str], str]
"""A function that takes a value and a format specifier and returns a formatted string."""

type MatcherAndFormatter = tuple[str | FormatMatcher, CustomFormatter]
"""
A pair of a matcher and its corresponding formatter.

The matcher is used to determine if the formatter should be applied to a given 
format specifier. If the matcher is a string, it must exactly match the format
specifier. If it is a FormatMatcher, it is called with the format specifier and
should return True if the formatter should be used.
"""


def _matcher_matches(matcher: str | FormatMatcher, format_spec: str) -> bool:
    """Check if a matcher matches a given format specifier."""
    return matcher == format_spec if isinstance(matcher, str) else matcher(format_spec)


def _format_interpolation(
    value: object,
    format_spec: str,
    conversion: t.Literal["a", "r", "s"] | None,
    *,
    formatters: t.Sequence[MatcherAndFormatter],
) -> object:
    converted = convert(value, conversion)
    if format_spec:
        for matcher, formatter in formatters:
            if _matcher_matches(matcher, format_spec):
                return formatter(converted, format_spec)
        return format(converted, format_spec)
    return converted


def format_interpolation(
    interpolation: Interpolation,
    *,
    formatters: t.Sequence[MatcherAndFormatter] = tuple(),
) -> object:
    """
    Format an Interpolation's value according to its format spec and conversion.

    PEP 750 allows t-string processing code to decide whether, and how, to
    interpret format specifiers. This function takes an optional sequence of
    (matcher, formatter) pairs. If a matcher returns True for the given format
    spec, the corresponding formatter is used to format the value. If no
    matchers match, the default formatting behavior is used.

    Conversions are always applied before formatting.
    """
    return _format_interpolation(
        interpolation.value,
        interpolation.format_spec,
        interpolation.conversion,
        formatters=formatters,
    )
