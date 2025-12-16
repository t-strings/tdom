import sys
import typing as t
from collections.abc import Iterable
from functools import lru_cache
from string.templatelib import Interpolation, Template

from markupsafe import Markup

from .callables import get_callable_info
from .classnames import classnames
from .nodes import Comment, DocumentType, Element, Fragment, Node, Text
from .parser import (
    HTMLAttribute,
    HTMLAttributesDict,
    TAttribute,
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TemplateParser,
    TFragment,
    TInterpolatedAttribute,
    TLiteralAttribute,
    TNode,
    TSpreadAttribute,
    TTemplatedAttribute,
    TText,
)
from .placeholders import TemplateRef
from .templating import format_interpolation, render_template_as_f, template_from_parts
from .utils import CachableTemplate, LastUpdatedOrderedDict


@t.runtime_checkable
class HasHTMLDunder(t.Protocol):
    def __html__(self) -> str: ...  # pragma: no cover


@lru_cache(maxsize=0 if "pytest" in sys.modules else 512)
def _parse_and_cache(cachable: CachableTemplate) -> TNode:
    return TemplateParser.parse(cachable.template)


type Attribute = tuple[str, object]
type AttributesDict = dict[str, object]

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


def _process_aria_attr(value: object) -> t.Iterable[HTMLAttribute]:
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


def _process_data_attr(value: object) -> t.Iterable[Attribute]:
    """Produce data-* attributes based on the interpolated value for "data"."""
    d = _force_dict(value, kind="data")
    for sub_k, sub_v in d.items():
        if sub_v is True:
            yield f"data-{sub_k}", True
        elif sub_v is not False and sub_v is not None:
            yield f"data-{sub_k}", str(sub_v)


def _process_class_attr(value: object) -> t.Iterable[HTMLAttribute]:
    """Substitute a class attribute based on the interpolated value."""
    yield ("class", classnames(value))


def _process_style_attr(value: object) -> t.Iterable[HTMLAttribute]:
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


def _substitute_spread_attrs(value: object) -> t.Iterable[Attribute]:
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


def _process_attr(key: str, value: object) -> t.Iterable[Attribute]:
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


def _resolve_t_attrs(
    attrs: t.Sequence[TAttribute], interpolations: tuple[Interpolation, ...]
) -> AttributesDict:
    """
    Replace placeholder values in attributes with their interpolated values.

    The values returned are not yet processed for HTML output; that is handled
    in a later step.
    """
    new_attrs: AttributesDict = LastUpdatedOrderedDict()
    for attr in attrs:
        match attr:
            case TLiteralAttribute(name=name, value=value):
                new_attrs[name] = True if value is None else value
            case TInterpolatedAttribute(name=name, value_i_index=i_index):
                interpolation = interpolations[i_index]
                attr_value = format_interpolation(interpolation)
                for sub_k, sub_v in _process_attr(name, attr_value):
                    new_attrs[sub_k] = sub_v
            case TTemplatedAttribute(name=name, value_ref=ref):
                attr_t = _resolve_ref(ref, interpolations)
                attr_value = render_template_as_f(attr_t)
                new_attrs[name] = attr_value
            case TSpreadAttribute(i_index=i_index):
                interpolation = interpolations[i_index]
                spread_value = format_interpolation(interpolation)
                for sub_k, sub_v in _substitute_spread_attrs(spread_value):
                    new_attrs[sub_k] = sub_v
            case _:
                raise ValueError(f"Unknown TAttribute type: {type(attr).__name__}")
    return new_attrs


def _resolve_html_attrs(attrs: AttributesDict) -> HTMLAttributesDict:
    """Resolve attribute values for HTML output."""
    html_attrs: HTMLAttributesDict = {}
    for key, value in attrs.items():
        match value:
            case True:
                html_attrs[key] = None
            case False | None:
                pass
            case _:
                html_attrs[key] = str(value)
    return html_attrs


def _resolve_attrs(
    attrs: t.Sequence[TAttribute], interpolations: tuple[Interpolation, ...]
) -> HTMLAttributesDict:
    """
    Substitute placeholders in attributes for HTML elements.

    This is the full pipeline: interpolation + HTML processing.
    """
    interpolated_attrs = _resolve_t_attrs(attrs, interpolations)
    return _resolve_html_attrs(interpolated_attrs)


def _flatten_nodes(nodes: t.Iterable[Node]) -> list[Node]:
    """Flatten a list of Nodes, expanding any Fragments."""
    flat: list[Node] = []
    for node in nodes:
        if isinstance(node, Fragment):
            flat.extend(node.children)
        else:
            flat.append(node)
    return flat


def _substitute_and_flatten_children(
    children: t.Iterable[TNode], interpolations: tuple[Interpolation, ...]
) -> list[Node]:
    """Substitute placeholders in a list of children and flatten any fragments."""
    resolved = [_resolve_t_node(child, interpolations) for child in children]
    flat = _flatten_nodes(resolved)
    return flat


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
    attrs: AttributesDict,
    children: list[Node],
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

    kwargs: AttributesDict = {}

    # Add all supported attributes
    for attr_name, attr_value in attrs.items():
        snake_name = _kebab_to_snake(attr_name)
        if snake_name in callable_info.named_params or callable_info.kwargs:
            kwargs[snake_name] = attr_value

    # Add children if appropriate
    if "children" in callable_info.named_params or callable_info.kwargs:
        kwargs["children"] = tuple(children)

    # Check to make sure we've fully satisfied the callable's requirements
    missing = callable_info.required_named_params - kwargs.keys()
    if missing:
        raise TypeError(
            f"Missing required parameters for component: {', '.join(missing)}"
        )

    result = value(**kwargs)
    return _node_from_value(result)


def _resolve_ref(
    ref: TemplateRef, interpolations: tuple[Interpolation, ...]
) -> Template:
    resolved = [interpolations[i_index] for i_index in ref.i_indexes]
    return template_from_parts(ref.strings, resolved)


def _resolve_t_text_ref(
    ref: TemplateRef, interpolations: tuple[Interpolation, ...]
) -> Text | Fragment:
    """Resolve a TText ref into Text or Fragment by processing interpolations."""
    if ref.is_literal:
        return Text(ref.strings[0])

    parts = [
        Text(part)
        if isinstance(part, str)
        else _node_from_value(format_interpolation(part))
        for part in _resolve_ref(ref, interpolations)
    ]
    flat = _flatten_nodes(parts)

    if len(flat) == 1 and isinstance(flat[0], Text):
        return flat[0]

    return Fragment(children=flat)


def _resolve_t_node(t_node: TNode, interpolations: tuple[Interpolation, ...]) -> Node:
    """Resolve a TNode tree into a Node tree by processing interpolations."""
    match t_node:
        case TText(ref=ref):
            return _resolve_t_text_ref(ref, interpolations)
        case TComment(ref=ref):
            comment_t = _resolve_ref(ref, interpolations)
            comment = render_template_as_f(comment_t)
            return Comment(comment)
        case TDocumentType(text=text):
            return DocumentType(text)
        case TFragment(children=children):
            resolved_children = _substitute_and_flatten_children(
                children, interpolations
            )
            return Fragment(children=resolved_children)
        case TElement(tag=tag, attrs=attrs, children=children):
            resolved_attrs = _resolve_attrs(attrs, interpolations)
            resolved_children = _substitute_and_flatten_children(
                children, interpolations
            )
            return Element(tag=tag, attrs=resolved_attrs, children=resolved_children)
        case TComponent(
            start_i_index=start_i_index,
            end_i_index=end_i_index,
            attrs=t_attrs,
            children=children,
        ):
            start_interpolation = interpolations[start_i_index]
            end_interpolation = (
                None if end_i_index is None else interpolations[end_i_index]
            )
            resolved_attrs = _resolve_t_attrs(t_attrs, interpolations)
            resolved_children = _substitute_and_flatten_children(
                children, interpolations
            )
            # HERE ALSO BE DRAGONS: validate matching start/end callables, since
            # the underlying TemplateParser cannot do that for us.
            if (
                end_interpolation is not None
                and end_interpolation.value != start_interpolation.value
            ):
                raise TypeError("Mismatched component start and end callables.")
            return _invoke_component(
                attrs=resolved_attrs,
                children=resolved_children,
                interpolation=start_interpolation,
            )
        case _:
            raise ValueError(f"Unknown TNode type: {type(t_node).__name__}")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def html(template: Template) -> Node:
    """Parse an HTML t-string, substitue values, and return a tree of Nodes."""
    cachable = CachableTemplate(template)
    t_node = _parse_and_cache(cachable)
    return _resolve_t_node(t_node, template.interpolations)
