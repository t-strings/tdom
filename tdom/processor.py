import sys
import typing as t
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from string.templatelib import Interpolation, Template

from markupsafe import Markup

from .callables import get_callable_info
from .classnames import classnames
from .nodes import Element, Fragment, Node, Text
from .parser import parse_html


@t.runtime_checkable
class HasHTMLDunder(t.Protocol):
    def __html__(self) -> str: ...  # pragma: no cover


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


def _process_aria_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
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


def _process_data_attr(value: object) -> t.Iterable[tuple[str, object | None]]:
    """Produce data-* attributes based on the interpolated value for "data"."""
    d = _force_dict(value, kind="data")
    for sub_k, sub_v in d.items():
        if sub_v is True:
            yield f"data-{sub_k}", True
        elif sub_v not in (False, None):
            yield f"data-{sub_k}", str(sub_v)


def _process_class_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Substitute a class attribute based on the interpolated value."""
    yield ("class", classnames(value))


def _process_style_attr(value: object) -> t.Iterable[tuple[str, str | None]]:
    """Substitute a style attribute based on the interpolated value."""
    if isinstance(value, str):
        yield ("style", value)
        return
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
        yield from _process_attr(sub_k, sub_v)


# A collection of custom handlers for certain attribute names that have
# special semantics. This is in addition to the special-casing in
# _substitute_attr() itself.
CUSTOM_ATTR_PROCESSORS = {
    "class": _process_class_attr,
    "data": _process_data_attr,
    "style": _process_style_attr,
    "aria": _process_aria_attr,
}


def _process_attr(
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
    if custom_processor := CUSTOM_ATTR_PROCESSORS.get(key):
        yield from custom_processor(value)
        return
    yield (key, value)


def _process_static_attr(
    key: str, value: str | None
) -> t.Iterable[tuple[str, object | None]]:
    """
    Bring static attributes, parsed from html but without interpolations, into the pipeline.
    """
    match value:
        case None:
            yield (key, True)
        case _:
            yield (key, value)


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
                for sub_k, sub_v in _process_attr(key, new_value):
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
            for sub_k, sub_v in _process_static_attr(key, value):
                new_attrs[sub_k] = sub_v
    return new_attrs


def _process_html_attrs(attrs: dict[str, object]) -> dict[str, str | None]:
    """
    Process attributes for HTML elements.

    This handles steps (2) and (3): special attribute name handling and
    value type processing (True -> None, False -> omit, etc.)
    """
    processed_attrs: dict[str, str | None] = {}
    for key, value in attrs.items():
        match value:
            case True:
                processed_attrs[key] = None
            case False | None:
                pass
            case _:
                processed_attrs[key] = str(value)
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
