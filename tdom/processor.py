import typing as t
from collections.abc import Iterable
from collections import OrderedDict
from string.templatelib import Interpolation, Template

from markupsafe import Markup

from .callables import get_callable_info
from .classnames import classnames
from .nodes import (
    TNode,
    TElement,
    TComponent,
    TFragment,
    TText,
    TComment,
    TDocumentType,
    Node,
    Element,
    Fragment,
    Text,
    Comment,
    DocumentType,
    TAttribute,
    SpreadAttribute,
    StaticAttribute,
    InterpolatedAttribute,
    TemplatedAttribute,
)
from .parser import parse_html
from .escaping import format_interpolation


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
        elif sub_v is not False and sub_v is not None:
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


class LastUpdatedOrderedDict(OrderedDict):
    "Store items in the order the keys were last added"

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)


def _substitute_interpolated_attrs(
    attrs: tuple[TAttribute, ...],
    interpolations: tuple[Interpolation, ...],
) -> dict[str, object | None]:
    """
    Replace placeholder values in attributes with their interpolated values.
    """
    new_attrs: dict[str, object | None] = LastUpdatedOrderedDict()
    for attr in attrs:
        match attr:
            case SpreadAttribute(interpolation_index=interpolation_index):
                interpolation = interpolations[interpolation_index]
                spread_value = format_interpolation(interpolation)
                for sub_k, sub_v in _substitute_spread_attrs(spread_value):
                    new_attrs[sub_k] = sub_v
            case StaticAttribute(name=name, value=value):
                new_attrs[name] = True if value is None else value
            case InterpolatedAttribute(
                name=name, interpolation_index=interpolation_index
            ):
                interpolation = interpolations[interpolation_index]
                new_value = format_interpolation(interpolation)
                for sub_k, sub_v in _process_attr(name, new_value):
                    new_attrs[sub_k] = sub_v
            case TemplatedAttribute(name=name, value_t=value_t):
                new_attrs[name] = "".join(
                    part
                    if isinstance(part, str)
                    else str(format_interpolation(interpolations[part.value]))
                    for part in value_t
                )
    return new_attrs


def _process_html_attrs(attrs: dict[str, object | None]) -> dict[str, str | None]:
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
    attrs: tuple[TAttribute, ...],
    interpolations: tuple[Interpolation, ...],
) -> dict[str, str | None]:
    """
    Substitute placeholders in attributes for HTML elements.

    This is the full pipeline: interpolation + HTML processing.
    """
    interpolated_attrs = _substitute_interpolated_attrs(attrs, interpolations)
    return _process_html_attrs(interpolated_attrs)


def _substitute_and_flatten_children(
    children: t.Iterable[TNode], interpolations: tuple[Interpolation, ...]
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


def _substitute_node(tnode: TNode, interpolations: tuple[Interpolation, ...]) -> Node:
    """Substitute placeholders in a node based on the corresponding interpolations."""
    match tnode:
        case TComment(text_t):
            chunks = []
            for part in text_t:
                if isinstance(part, str):
                    chunks.append(part)
                else:
                    chunks.append(str(format_interpolation(interpolations[part.value])))
            return Comment("".join(chunks))
        case TText(text_t):
            parts = list(text_t)
            if not parts:
                return Text("")
            elif len(parts) == 1 and isinstance(parts[0], str):
                return Text(parts[0])
            else:
                f = Fragment(children=[])
                for part in parts:
                    if isinstance(part, str):
                        f.children.append(Text(part))
                    else:
                        res = _node_from_value(
                            format_interpolation(interpolations[part.value])
                        )
                        if isinstance(res, Fragment):
                            if res.children:
                                f.children.extend(res.children)
                        else:
                            f.children.append(res)
                if len(f.children) == 1:
                    return f.children[0]
                return f
        case TComponent() as component:
            # Runtime check
            if (
                component.starttag_interpolation_index
                != component.endtag_interpolation_index
                and interpolations[component.starttag_interpolation_index].value
                != interpolations[component.endtag_interpolation_index].value
            ):
                raise ValueError(
                    "Opening component tag's interpolation must match closing interpolation."
                )
            new_children = _substitute_and_flatten_children(
                component.children, interpolations
            )
            component_attrs = _substitute_interpolated_attrs(
                component.attrs, interpolations
            )
            return _invoke_component(
                component_attrs,
                new_children,
                interpolations[component.starttag_interpolation_index],
            )
        case TElement(tag=tag, attrs=attrs, children=children):
            new_children = _substitute_and_flatten_children(children, interpolations)
            html_attrs = _substitute_attrs(attrs, interpolations)
            return Element(tag=tag, attrs=html_attrs, children=new_children)
        case TFragment(children=children):
            new_children = _substitute_and_flatten_children(children, interpolations)
            return Fragment(children=new_children)
        case TDocumentType():
            return DocumentType(tnode.text)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def html(template: Template) -> Node:
    """Parse a t-string and return a tree of Nodes."""
    # Parse the HTML, returning a tree of nodes with placeholders
    # where interpolations go.
    tnode = parse_html(template)
    return _substitute_node(tnode, template.interpolations)
