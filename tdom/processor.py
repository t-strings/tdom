import random
import string
import sys
import typing as t
from collections.abc import Iterable
from functools import lru_cache
from string.templatelib import Interpolation, Template

from markupsafe import Markup

from .classnames import classnames
from .nodes import Element, Fragment, Node, Text
from .parser import parse_html
from .utils import format_interpolation as base_format_interpolation


@t.runtime_checkable
class HasHTMLDunder(t.Protocol):
    def __html__(self) -> str: ...


# --------------------------------------------------------------------------
# Value formatting
# --------------------------------------------------------------------------


def _format_safe(value: object, format_spec: str) -> str:
    """Use Markup() to mark a value as safe HTML."""
    assert format_spec == "safe"
    return Markup(value)


def _format_unsafe(value: object, format_spec: str) -> str:
    """Convert a value to a plain string, forcing it to be treated as unsafe."""
    assert format_spec == "unsafe"
    return str(value)


CUSTOM_FORMATTERS = (("safe", _format_safe), ("unsafe", _format_unsafe))


def format_interpolation(interpolation: Interpolation) -> object:
    return base_format_interpolation(
        interpolation,
        formatters=CUSTOM_FORMATTERS,
    )


# --------------------------------------------------------------------------
# Instrumentation, Parsing, and Caching
# --------------------------------------------------------------------------

_PLACEHOLDER_PREFIX = f"t🐍-{''.join(random.choices(string.ascii_lowercase, k=4))}-"
_PP_LEN = len(_PLACEHOLDER_PREFIX)


def _placeholder(i: int) -> str:
    """Generate a placeholder for the i-th interpolation."""
    return f"{_PLACEHOLDER_PREFIX}{i}"


def _placholder_index(s: str) -> int:
    """Extract the index from a placeholder string."""
    return int(s[_PP_LEN:])


def _instrument(
    strings: tuple[str, ...], callable_ids: tuple[int | None, ...]
) -> t.Iterable[str]:
    """
    Join the strings with placeholders in between where interpolations go.

    This is used to prepare the template string for parsing, so that we can
    later substitute the actual interpolated values into the parse tree.

    The placeholders are chosen to be unlikely to collide with typical HTML
    content.
    """
    count = len(strings)

    callable_placeholders: dict[int, str] = {}

    for i, s in enumerate(strings):
        yield s
        # There are always count-1 placeholders between count strings.
        if i < count - 1:
            placeholder = _placeholder(i)

            # Special case for component callables: if the interpolation
            # is a callable, we need to make sure that any matching closing
            # tag uses the same placeholder.
            callable_id = callable_ids[i]
            if callable_id:
                placeholder = callable_placeholders.setdefault(callable_id, placeholder)

            yield placeholder


@lru_cache(maxsize=0 if "pytest" in sys.modules else 256)
def _instrument_and_parse_internal(
    strings: tuple[str, ...], callable_ids: tuple[int | None, ...]
) -> Node:
    """
    Instrument the strings and parse the resulting HTML.

    The result is cached to avoid re-parsing the same template multiple times.
    """
    instrumented = _instrument(strings, callable_ids)
    return parse_html(instrumented)


def _callable_id(value: object) -> int | None:
    """Return a unique identifier for a callable, or None if not callable."""
    return id(value) if callable(value) else None


def _instrument_and_parse(template: Template) -> Node:
    """Instrument and parse a template, returning a tree of Nodes."""
    # This is a thin wrapper around the cached internal function that does the
    # actual work. This exists to handle the syntax we've settled on for
    # component invocation, namely that callables are directly included as
    # interpolations both in the open *and* the close tags. We need to make
    # sure that matching tags... match!
    #
    # If we used `tdom`'s approach of component closing tags of <//> then we
    # wouldn't have to do this. But I worry that tdom's syntax is harder to read
    # (it's easy to miss the closing tag) and may prove unfamiliar for
    # users coming from other templating systems.
    callable_ids = tuple(
        _callable_id(interpolation.value) for interpolation in template.interpolations
    )
    return _instrument_and_parse_internal(template.strings, callable_ids)


# --------------------------------------------------------------------------
# Placeholder Substitution
# --------------------------------------------------------------------------


def _force_dict(value: t.Any, *, kind: str) -> dict:
    """Try to convert a value to a dict, raising TypeError if not possible."""
    try:
        return dict(value)
    except (TypeError, ValueError):
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for {kind} attributes"
        ) from None


def _substitute_aria_attrs(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Produce aria-* attributes based on the interpolated value for "aria"."""
    d = _force_dict(value, kind="aria")
    for sub_k, sub_v in d.items():
        if sub_v is True:
            yield f"aria-{sub_k}", "true"
        elif sub_v is False:
            yield f"aria-{sub_k}", "false"
        elif sub_v is None:
            pass
        else:
            yield f"aria-{sub_k}", str(sub_v)


def _substitute_data_attrs(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Produce data-* attributes based on the interpolated value for "data"."""
    d = _force_dict(value, kind="data")
    for sub_k, sub_v in d.items():
        if sub_v is True:
            yield f"data-{sub_k}", None
        elif sub_v not in (False, None):
            yield f"data-{sub_k}", str(sub_v)


def _substitute_class_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Substitute a class attribute based on the interpolated value."""
    yield ("class", classnames(value))


def _substitute_style_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Substitute a style attribute based on the interpolated value."""
    try:
        d = _force_dict(value, kind="style")
        style_str = "; ".join(f"{k}: {v}" for k, v in d.items())
        yield ("style", style_str)
    except TypeError:
        yield ("style", str(value))


def _substitute_spread_attrs(
    value: object,
) -> t.Iterable[tuple[str, object | None]]:
    """
    Substitute a spread attribute based on the interpolated value.

    A spread attribute is one where the key is a placeholder, indicating that
    the entire attribute set should be replaced by the interpolated value.
    The value must be a dict or iterable of key-value pairs.
    """
    d = _force_dict(value, kind="spread")
    for sub_k, sub_v in d.items():
        yield from _substitute_attr(sub_k, sub_v)


# A collection of custom handlers for certain attribute names that have
# special semantics. This is in addition to the special-casing in
# _substitute_attr() itself.
CUSTOM_ATTR_HANDLERS = {
    "class": _substitute_class_attr,
    "data": _substitute_data_attrs,
    "style": _substitute_style_attr,
    "aria": _substitute_aria_attrs,
}


def _substitute_attr(
    key: str,
    value: object,
) -> t.Iterable[tuple[str, object | None]]:
    """
    Substitute a single attribute based on its key and the interpolated value.

    A single parsed attribute with a placeholder may result in multiple
    attributes in the final output, for instance if the value is a dict or
    iterable of key-value pairs. Likewise, a value of False will result in
    the attribute being omitted entirely; nothing is yielded in that case.
    """
    # Special handling for certain attribute names that have special semantics
    if custom_handler := CUSTOM_ATTR_HANDLERS.get(key):
        yield from custom_handler(value)
        return

    # General handling for all other attributes:
    match value:
        case True:
            yield (key, None)
        case False | None:
            pass
        case _:
            yield (key, value)


def _substitute_attrs(
    attrs: dict[str, str | None], interpolations: tuple[Interpolation, ...]
) -> dict[str, object | None]:
    """Substitute placeholders in attributes based on the corresponding interpolations."""
    new_attrs: dict[str, object | None] = {}
    for key, value in attrs.items():
        if value and value.startswith(_PLACEHOLDER_PREFIX):
            index = _placholder_index(value)
            interpolation = interpolations[index]
            value = format_interpolation(interpolation)
            for sub_k, sub_v in _substitute_attr(key, value):
                new_attrs[sub_k] = sub_v
        elif key.startswith(_PLACEHOLDER_PREFIX):
            index = _placholder_index(key)
            interpolation = interpolations[index]
            value = format_interpolation(interpolation)
            for sub_k, sub_v in _substitute_spread_attrs(value):
                new_attrs[sub_k] = sub_v
        else:
            new_attrs[key] = value
    return new_attrs


def _substitute_and_flatten_children(
    children: t.Iterable[Node], interpolations: tuple[Interpolation, ...]
) -> list[Node]:
    """Substitute placeholders in a list of children and flatten any fragments."""
    new_children: list[Node] = []
    for child in children:
        substituted = _substitute_node(child, interpolations)
        if isinstance(substituted, Fragment):
            # This can happen if an interpolation results in a Fragment, for
            # instance if it is iterable.
            new_children.extend(substituted.children)
        else:
            new_children.append(substituted)
    return new_children


def _node_from_value(value: object) -> Node:
    """
    Convert an arbitrary value to a Node.

    This is the primary action performed when replacing interpolations in child
    content positions.
    """
    match value:
        case str():
            return Text(value)
        case Node():
            return value
        case Template():
            return html(value)
        # Consider: falsey values, not just False and None?
        case False | None:
            return Fragment(children=[])
        case Iterable():
            children = [_node_from_value(v) for v in value]
            return Fragment(children=children)
        case HasHTMLDunder():
            # CONSIDER: should we do this lazily?
            return Text(Markup(value.__html__()))
        case c if callable(c):
            # Treat all callable values in child content positions as if
            # they are zero-arg functions that return a value to be rendered.
            return _node_from_value(c())
        case _:
            # CONSIDER: should we do this lazily?
            return Text(str(value))


def _invoke_component(
    tag: str,
    new_attrs: dict[str, object | None],
    new_children: list[Node],
    interpolations: tuple[Interpolation, ...],
) -> Node:
    """Substitute a component invocation based on the corresponding interpolations."""
    index = _placholder_index(tag)
    interpolation = interpolations[index]
    value = format_interpolation(interpolation)
    if not callable(value):
        raise TypeError(
            f"Expected a callable for component invocation, got {type(value).__name__}"
        )
    # Replace attr names hyphens with underscores for Python kwargs
    kwargs = {k.replace("-", "_"): v for k, v in new_attrs.items()}

    # Call the component and return the resulting node
    # TODO: handle failed calls more gracefully; consider using signature()?
    result = value(*new_children, **kwargs)
    return _node_from_value(result)


def _stringify_attrs(attrs: dict[str, object | None]) -> dict[str, str | None]:
    """Convert all attribute values to strings, preserving None values."""
    return {k: str(v) if v is not None else None for k, v in attrs.items()}


def _substitute_node(p_node: Node, interpolations: tuple[Interpolation, ...]) -> Node:
    """Substitute placeholders in a node based on the corresponding interpolations."""
    match p_node:
        case Text(text) if str(text).startswith(_PLACEHOLDER_PREFIX):
            index = _placholder_index(str(text))
            interpolation = interpolations[index]
            value = format_interpolation(interpolation)
            return _node_from_value(value)
        case Element(tag=tag, attrs=attrs, children=children):
            new_attrs = _substitute_attrs(attrs, interpolations)
            new_children = _substitute_and_flatten_children(children, interpolations)
            if tag.startswith(_PLACEHOLDER_PREFIX):
                return _invoke_component(tag, new_attrs, new_children, interpolations)
            else:
                new_attrs = _stringify_attrs(new_attrs)
                return Element(tag=tag, attrs=new_attrs, children=new_children)
        case Fragment(children=children):
            new_children = _substitute_and_flatten_children(children, interpolations)
            return Fragment(children=new_children)
        case _:
            return p_node


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def html(template: Template) -> Node:
    """Parse a t-string and return a tree of Nodes."""
    # Parse the HTML, returning a tree of nodes with placeholders
    # where interpolations go.
    p_node = _instrument_and_parse(template)
    return _substitute_node(p_node, template.interpolations)
