from enum import Enum, auto
import random
import re
import string
import sys
import typing as t
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from string.templatelib import Interpolation, Template

from markupsafe import Markup

from .callables import CallableInfo, get_callable_info
from .classnames import classnames
from .nodes import Element, Fragment, Node, Text
from .parser import parse_html
from .utils import format_interpolation as base_format_interpolation


@t.runtime_checkable
class HasHTMLDunder(t.Protocol):
    def __html__(self) -> str: ...  # pragma: no cover


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

_PLACEHOLDER_PREFIX = f"t🐍{''.join(random.choices(string.ascii_lowercase, k=2))}-"
_PLACEHOLDER_SUFFIX = f"-{''.join(random.choices(string.ascii_lowercase, k=2))}🐍t"
_PLACEHOLDER_PATTERN = re.compile(
    re.escape(_PLACEHOLDER_PREFIX) + r"(\d+)" + re.escape(_PLACEHOLDER_SUFFIX)
)


def _placeholder(i: int) -> str:
    """Generate a placeholder for the i-th interpolation."""
    return f"{_PLACEHOLDER_PREFIX}{i}{_PLACEHOLDER_SUFFIX}"


@dataclass(frozen=True, slots=True)
class _PlaceholderMatch:
    start: int
    end: int
    index: int | None


def _find_placeholder(s: str) -> int | None:
    """
    If the string is exactly one placeholder, return its index. Otherwise, None.
    """
    match = _PLACEHOLDER_PATTERN.fullmatch(s)
    return int(match.group(1)) if match else None


def _find_all_placeholders(s: str) -> t.Iterable[_PlaceholderMatch]:
    """
    Find all placeholders in a string, returning their positions and indices.

    If there is non-placeholder text in the string, its position is also
    returned with index None.
    """
    matches = list(_PLACEHOLDER_PATTERN.finditer(s))
    last_end = 0
    for match in matches:
        if match.start() > last_end:
            yield _PlaceholderMatch(last_end, match.start(), None)
        index = int(match.group(1))
        yield _PlaceholderMatch(match.start(), match.end(), index)
        last_end = match.end()
    if last_end < len(s):
        yield _PlaceholderMatch(last_end, len(s), None)


def _replace_placeholders(
    value: str, interpolations: tuple[Interpolation, ...]
) -> tuple[bool, object]:
    """
    Replace any placeholders embedded within a string attribute value.

    If there are no placeholders, return False and the original string.

    If there is exactly one placeholder and nothing else, return True and the
    corresponding interpolation value.

    If there are multiple placeholders or surrounding text, return True and
    a concatenated string with all placeholders replaced and interpolations
    formatted and converted to strings.
    """
    matches = tuple(_find_all_placeholders(value))

    # Case 1: No placeholders found
    if len(matches) == 1 and matches[0].index is None:
        return False, value

    # Case 2: Single placeholder and no surrounding text
    if len(matches) == 1 and matches[0].index is not None:
        index = matches[0].index
        formatted = format_interpolation(interpolations[index])
        return True, formatted

    # Case 3: Multiple placeholders or surrounding text
    parts = [
        value[match.start : match.end]
        if match.index is None
        else str(format_interpolation(interpolations[match.index]))
        for match in matches
    ]
    return True, "".join(parts)


def _instrument(
    strings: tuple[str, ...], callable_infos: tuple[CallableInfo | None, ...]
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
            callable_info = callable_infos[i]
            if callable_info:
                placeholder = callable_placeholders.setdefault(
                    callable_info.id, placeholder
                )

            yield placeholder


@lru_cache(maxsize=0 if "pytest" in sys.modules else 512)
def _instrument_and_parse_internal(
    strings: tuple[str, ...], callable_infos: tuple[CallableInfo | None, ...]
) -> Node:
    """
    Instrument the strings and parse the resulting HTML.

    The result is cached to avoid re-parsing the same template multiple times.
    """
    instrumented = _instrument(strings, callable_infos)
    return parse_html(instrumented)


def _callable_info(value: object) -> CallableInfo | None:
    """Return a unique identifier for a callable, or None if not callable."""
    return get_callable_info(value) if callable(value) else None


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
    callable_infos = tuple(
        _callable_info(interpolation.value) for interpolation in template.interpolations
    )
    return _instrument_and_parse_internal(template.strings, callable_infos)


# --------------------------------------------------------------------------
# Placeholder Substitution
# --------------------------------------------------------------------------
class AttrMarker(Enum):
    """
    Use attr markers to keep track of intention AND actual value during
    processing.
    """
    REMOVE_ATTR_FALSE = auto()
    REMOVE_ATTR_NONE = auto()
    BARE_ATTR_TRUE = auto()
    BARE_ATTR_NONE = auto()


def _force_dict(value: t.Any, *, kind: str) -> dict:
    """Try to convert a value to a dict, raising TypeError if not possible."""
    try:
        return dict(value)
    except (TypeError, ValueError):
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for {kind} attributes"
        ) from None


def _process_aria_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Produce aria-* attributes based on the interpolated value for "aria"."""
    d = _force_dict(value, kind="aria")
    for sub_k, sub_v in d.items():
        if sub_v is True:
            yield f"aria-{sub_k}", "true"
        elif sub_v is False:
            yield f"aria-{sub_k}", "false"
        elif sub_v is None:
            yield f"aria-{sub_k}", AttrMarker.REMOVE_ATTR_NONE
        else:
            yield f"aria-{sub_k}", str(sub_v)


def _process_data_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Produce data-* attributes based on the interpolated value for "data"."""
    d = _force_dict(value, kind="data")
    for sub_k, sub_v in d.items():
        if sub_v is True:
            yield f"data-{sub_k}", None
        elif sub_v is False:
            yield f"data-{sub_k}", AttrMarker.REMOVE_ATTR_FALSE
        elif sub_v is None:
            yield f"data-{sub_k}", AttrMarker.REMOVE_ATTR_NONE
        else:
            yield f"data-{sub_k}", str(sub_v)


def _process_class_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Substitute a class attribute based on the interpolated value."""
    if value is None:
        yield f"class", AttrMarker.REMOVE_ATTR_NONE
    elif value is not False:
        yield ("class", classnames(value))


def _process_style_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Substitute a style attribute based on the interpolated value."""
    if isinstance(value, str):
        yield ("style", value)
        return
    elif value is None:
        yield ("style", AttrMarker.REMOVE_ATTR_NONE)
    try:
        d = _force_dict(value, kind="style")
        style_str = "; ".join(f"{k}: {v}" for k, v in d.items())
        yield ("style", style_str)
    except TypeError:
        raise TypeError("'style' attribute value must be a string or dict") from None


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
        yield from _process_dynamic_attr(sub_k, sub_v)


# A collection of custom handlers for certain attribute names that have
# special semantics. This is in addition to the special-casing in
# _substitute_attr() itself.
CUSTOM_ATTR_PROCESSORS = {
    "class": _process_class_attr,
    "data": _process_data_attr,
    "style": _process_style_attr,
    "aria": _process_aria_attr,
}


def _process_dynamic_attr(
    key: str,
    value: object,
) -> t.Iterable[tuple[str, object | None]]:
    """
    Process a dynamically interpolated attribute that was either explicitly
    named or loaded via a spread attribute.

    A single parsed attribute with a placeholder may result in multiple
    attributes in the final output, for instance if the value is a dict or
    iterable of key-value pairs.

    NOTE: Custom processors are responsible for processing the attributes they
    generate, specifically they must apply markers when necessary.
    """
    # Special handling for certain attribute names that have special semantics
    if custom_processor := CUSTOM_ATTR_PROCESSORS.get(key):
        yield from custom_processor(value)
        return

    match value:
        case True:
            yield (key, AttrMarker.BARE_ATTR_TRUE)
        case False:
            yield (key, AttrMarker.REMOVE_ATTR_FALSE)
        case None:
            yield (key, AttrMarker.REMOVE_ATTR_NONE)
        case _:
            yield (key, value)


def _process_static_attr_value(
    value: str|None,
) -> str|AttrMarker:
    """
    Process statically parsed attributes before they are merged in.
    """
    return AttrMarker.BARE_ATTR_NONE if value is None else value


def _substitute_interpolated_attrs(
    attrs: dict[str, str | None], interpolations: tuple[Interpolation, ...]
) -> dict[str, object | None]:
    """
    Replace placeholder values in attributes with their interpolated values.

    This only handles step (1): value substitution. No special processing
    of attribute names or value types is performed.
    """
    new_attrs: dict[str, object | None] = {}
    for key, value in attrs.items():
        if value is not None:
            has_placeholders, new_value = _replace_placeholders(value, interpolations)
            if has_placeholders:
                for sub_k, sub_v in _process_dynamic_attr(key, new_value):
                    new_attrs[sub_k] = sub_v
                continue

        if (index := _find_placeholder(key)) is not None:
            # Spread attributes
            interpolation = interpolations[index]
            spread_value = format_interpolation(interpolation)
            for sub_k, sub_v in _substitute_spread_attrs(spread_value):
                new_attrs[sub_k] = sub_v
        else:
            # Static attribute
            new_attrs[key] = _process_static_attr_value(value)
    return new_attrs


def _process_html_attrs(attrs: dict[str, object]) -> dict[str, str | None]:
    """
    Process attributes for HTML elements.

    This handles steps (2) and (3): special attribute name handling and
    value type processing (True -> None, False -> omit, etc.)
    """
    processed_attrs: dict[str, str | None] = {}
    for key, value in attrs.items():
        if value in (AttrMarker.BARE_ATTR_TRUE, AttrMarker.BARE_ATTR_NONE):
            processed_attrs[key] = None
        elif value not in (AttrMarker.REMOVE_ATTR_FALSE, AttrMarker.REMOVE_ATTR_NONE):
            processed_attrs[key] = value
    return processed_attrs


def _substitute_attrs(
    attrs: dict[str, str | None], interpolations: tuple[Interpolation, ...]
) -> dict[str, str | None]:
    """
    Substitute placeholders in attributes for HTML elements.

    This is the full pipeline: interpolation + HTML processing.
    """
    interpolated_attrs = _substitute_interpolated_attrs(attrs, interpolations)
    return _process_html_attrs(interpolated_attrs)


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


def _kebab_to_snake(name: str) -> str:
    """Convert a kebab-case name to snake_case."""
    return name.replace("-", "_").lower()


def _invoke_component(
    new_attrs: dict[str, object | None],
    new_children: list[Node],
    interpolation: Interpolation,
) -> Node:
    """
    Invoke a component callable with the provided attributes and children.

    Components are any callable that meets the required calling signature.
    Typically, that's a function, but it could also be the constructor or
    __call__() method for a class; dataclass constructors match our expected
    invocation style.

    We validate the callable's signature and invoke it with keyword-only
    arguments, then convert the result to a Node.

    Component invocation rules:

    1. All arguments are passed as keywords only. Components cannot require
    positional arguments.

    2. Children are passed via a "children" parameter when:

    - Child content exists in the template AND
    - The callable accepts "children" OR has **kwargs

    If no children exist but the callable accepts "children", we pass an
    empty tuple.

    3. All other attributes are converted from kebab-case to snake_case
    and passed as keyword arguments if the callable accepts them (or has
    **kwargs). Attributes that don't match parameters are silently ignored.
    """
    value = format_interpolation(interpolation)
    if not callable(value):
        raise TypeError(
            f"Expected a callable for component invocation, got {type(value).__name__}"
        )
    callable_info = get_callable_info(value)

    if callable_info.requires_positional:
        raise TypeError(
            "Component callables cannot have required positional arguments."
        )

    kwargs: dict[str, object] = {}

    # Add all supported attributes
    for attr_name, attr_value in new_attrs.items():
        snake_name = _kebab_to_snake(attr_name)
        if snake_name in callable_info.named_params or callable_info.kwargs:
            if attr_value in (AttrMarker.REMOVE_ATTR_NONE, AttrMarker.BARE_ATTR_NONE):
                kwargs[snake_name] = None
            elif attr_value is AttrMarker.REMOVE_ATTR_FALSE:
                kwargs[snake_name] = False
            elif attr_value is AttrMarker.BARE_ATTR_TRUE:
                kwargs[snake_name] = True
            else:
                kwargs[snake_name] = attr_value

    # Add children if appropriate
    if "children" in callable_info.named_params or callable_info.kwargs:
        kwargs["children"] = tuple(new_children)

    # Check to make sure we've fully satisfied the callable's requirements
    missing = callable_info.required_named_params - kwargs.keys()
    if missing:
        raise TypeError(
            f"Missing required parameters for component: {', '.join(missing)}"
        )

    result = value(**kwargs)
    return _node_from_value(result)


def _substitute_node(p_node: Node, interpolations: tuple[Interpolation, ...]) -> Node:
    """Substitute placeholders in a node based on the corresponding interpolations."""
    match p_node:
        case Text(text) if (index := _find_placeholder(text)) is not None:
            interpolation = interpolations[index]
            value = format_interpolation(interpolation)
            return _node_from_value(value)
        case Element(tag=tag, attrs=attrs, children=children):
            new_children = _substitute_and_flatten_children(children, interpolations)
            if (index := _find_placeholder(tag)) is not None:
                component_attrs = _substitute_interpolated_attrs(attrs, interpolations)
                return _invoke_component(
                    component_attrs, new_children, interpolations[index]
                )
            else:
                html_attrs = _substitute_attrs(attrs, interpolations)
                return Element(tag=tag, attrs=html_attrs, children=new_children)
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
