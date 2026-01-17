import sys
import typing as t
from collections.abc import Iterable, Sequence, Callable
from functools import lru_cache
from string.templatelib import Interpolation, Template
from dataclasses import dataclass

from markupsafe import Markup

from .callables import get_callable_info, CallableInfo
from .format import format_interpolation as base_format_interpolation
from .format import format_template
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
from .template_utils import template_from_parts
from .utils import CachableTemplate, LastUpdatedOrderedDict


@t.runtime_checkable
class HasHTMLDunder(t.Protocol):
    def __html__(self) -> str: ...  # pragma: no cover


# TODO: in Ian's original PR, this caching was tethered to the
# TemplateParser. Here, it's tethered to the processor. I suspect we'll
# revisit this soon enough.


@lru_cache(maxsize=0 if "pytest" in sys.modules else 512)
def _parse_and_cache(cachable: CachableTemplate) -> TNode:
    return TemplateParser.parse(cachable.template)


type Attribute = tuple[str, object]
type AttributesDict = dict[str, object]


# --------------------------------------------------------------------------
# Custom formatting for the processor
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
# Placeholder Substitution
# --------------------------------------------------------------------------


def _expand_aria_attr(value: object) -> t.Iterable[HTMLAttribute]:
    """Produce aria-* attributes based on the interpolated value for "aria"."""
    if value is None:
        return
    elif isinstance(value, dict):
        for sub_k, sub_v in value.items():
            if sub_v is True:
                yield f"aria-{sub_k}", "true"
            elif sub_v is False:
                yield f"aria-{sub_k}", "false"
            elif sub_v is None:
                yield f"aria-{sub_k}", None
            else:
                yield f"aria-{sub_k}", str(sub_v)
    else:
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for aria attribute"
        )


def _expand_data_attr(value: object) -> t.Iterable[Attribute]:
    """Produce data-* attributes based on the interpolated value for "data"."""
    if value is None:
        return
    elif isinstance(value, dict):
        for sub_k, sub_v in value.items():
            if sub_v is True or sub_v is False or sub_v is None:
                yield f"data-{sub_k}", sub_v
            else:
                yield f"data-{sub_k}", str(sub_v)
    else:
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for data attribute"
        )


def _substitute_spread_attrs(value: object) -> t.Iterable[Attribute]:
    """
    Substitute a spread attribute based on the interpolated value.

    A spread attribute is one where the key is a placeholder, indicating that
    the entire attribute set should be replaced by the interpolated value.
    The value must be a dict or iterable of key-value pairs.
    """
    if value is None:
        return
    elif isinstance(value, dict):
        yield from value.items()
    else:
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for spread attributes"
        )


ATTR_EXPANDERS = {
    "data": _expand_data_attr,
    "aria": _expand_aria_attr,
}


def parse_style_attribute_value(style_str: str) -> list[tuple[str, str | None]]:
    """
    Parse the style declarations out of a style attribute string.
    """
    props = [p.strip() for p in style_str.split(";")]
    styles: list[tuple[str, str | None]] = []
    for prop in props:
        if prop:
            prop_parts = [p.strip() for p in prop.split(":") if p.strip()]
            if len(prop_parts) != 2:
                raise ValueError(
                    f"Invalid number of parts for style property {prop} in {style_str}"
                )
            styles.append((prop_parts[0], prop_parts[1]))
    return styles


def make_style_accumulator(old_value: object) -> StyleAccumulator:
    """
    Initialize the style accumulator.
    """
    match old_value:
        case str():
            styles = {
                name: value for name, value in parse_style_attribute_value(old_value)
            }
        case True:  # A bare attribute will just default to {}.
            styles = {}
        case _:
            raise TypeError(f"Unexpected value: {old_value}")
    return StyleAccumulator(styles=styles)


@dataclass
class StyleAccumulator:
    styles: dict[str, str | None]

    def merge_value(self, value: object) -> None:
        """
        Merge in an interpolated style value.
        """
        match value:
            case str():
                self.styles.update(
                    {name: value for name, value in parse_style_attribute_value(value)}
                )
            case dict():
                self.styles.update(
                    {
                        str(pn): str(pv) if pv is not None else None
                        for pn, pv in value.items()
                    }
                )
            case None:
                pass
            case _:
                raise TypeError(
                    f"Unknown interpolated style value {value}, use '' to omit."
                )

    def to_value(self) -> str | None:
        """
        Serialize the special style value back into a string.

        @NOTE: If the result would be `''` then use `None` to omit the attribute.
        """
        style_value = "; ".join(
            [f"{pn}: {pv}" for pn, pv in self.styles.items() if pv is not None]
        )
        return style_value if style_value else None


def make_class_accumulator(old_value: object) -> ClassAccumulator:
    """
    Initialize the class accumulator.
    """
    match old_value:
        case str():
            toggled_classes = {cn: True for cn in old_value.split()}
        case True:
            toggled_classes = {}
        case _:
            raise ValueError(f"Unexpected value {old_value}")
    return ClassAccumulator(toggled_classes=toggled_classes)


@dataclass
class ClassAccumulator:
    toggled_classes: dict[str, bool]

    def merge_value(self, value: object) -> None:
        """
        Merge in an interpolated class value.
        """
        if isinstance(value, dict):
            self.toggled_classes.update(
                {str(cn): bool(toggle) for cn, toggle in value.items()}
            )
        else:
            if not isinstance(value, str) and isinstance(value, Sequence):
                items = value[:]
            else:
                items = (value,)
            for item in items:
                match item:
                    case str():
                        self.toggled_classes.update({cn: True for cn in item.split()})
                    case None:
                        pass
                    case _:
                        if item == value:
                            raise TypeError(
                                f"Unknown interpolated class value: {value}"
                            )
                        else:
                            raise TypeError(
                                f"Unknown interpolated class item in {value}: {item}"
                            )

    def to_value(self) -> str | None:
        """
        Serialize the special class value back into a string.

        @NOTE: If the result would be `''` then use `None` to omit the attribute.
        """
        class_value = " ".join(
            [cn for cn, toggle in self.toggled_classes.items() if toggle]
        )
        return class_value if class_value else None


ATTR_ACCUMULATOR_MAKERS = {
    "class": make_class_accumulator,
    "style": make_style_accumulator,
}


type AttributeValueAccumulator = StyleAccumulator | ClassAccumulator


def _resolve_t_attrs(
    attrs: t.Sequence[TAttribute], interpolations: tuple[Interpolation, ...]
) -> AttributesDict:
    """
    Replace placeholder values in attributes with their interpolated values.

    The values returned are not yet processed for HTML output; that is handled
    in a later step.
    """
    new_attrs: AttributesDict = LastUpdatedOrderedDict()
    attr_accs: dict[str, AttributeValueAccumulator] = {}
    for attr in attrs:
        match attr:
            case TLiteralAttribute(name=name, value=value):
                attr_value = True if value is None else value
                if name in ATTR_ACCUMULATOR_MAKERS and name in new_attrs:
                    if name not in attr_accs:
                        attr_accs[name] = ATTR_ACCUMULATOR_MAKERS[name](new_attrs[name])
                    new_attrs[name] = attr_accs[name].merge_value(attr_value)
                else:
                    new_attrs[name] = attr_value
            case TInterpolatedAttribute(name=name, value_i_index=i_index):
                interpolation = interpolations[i_index]
                attr_value = format_interpolation(interpolation)
                if name in ATTR_ACCUMULATOR_MAKERS:
                    if name not in attr_accs:
                        attr_accs[name] = ATTR_ACCUMULATOR_MAKERS[name](
                            new_attrs.get(name, True)
                        )
                    new_attrs[name] = attr_accs[name].merge_value(attr_value)
                elif expander := ATTR_EXPANDERS.get(name):
                    for sub_k, sub_v in expander(attr_value):
                        new_attrs[sub_k] = sub_v
                else:
                    new_attrs[name] = attr_value
            case TTemplatedAttribute(name=name, value_ref=ref):
                attr_t = _resolve_ref(ref, interpolations)
                attr_value = format_template(attr_t)
                if name in ATTR_ACCUMULATOR_MAKERS:
                    if name not in attr_accs:
                        attr_accs[name] = ATTR_ACCUMULATOR_MAKERS[name](
                            new_attrs.get(name, True)
                        )
                    new_attrs[name] = attr_accs[name].merge_value(attr_value)
                elif expander := ATTR_EXPANDERS.get(name):
                    raise TypeError(f"{name} attributes cannot be templated")
                else:
                    new_attrs[name] = attr_value
            case TSpreadAttribute(i_index=i_index):
                interpolation = interpolations[i_index]
                spread_value = format_interpolation(interpolation)
                for sub_k, sub_v in _substitute_spread_attrs(spread_value):
                    if sub_k in ATTR_ACCUMULATOR_MAKERS:
                        if sub_k not in attr_accs:
                            attr_accs[sub_k] = ATTR_ACCUMULATOR_MAKERS[sub_k](
                                new_attrs.get(sub_k, True)
                            )
                        new_attrs[sub_k] = attr_accs[sub_k].merge_value(sub_v)
                    elif expander := ATTR_EXPANDERS.get(sub_k):
                        for exp_k, exp_v in expander(sub_v):
                            new_attrs[exp_k] = exp_v
                    else:
                        new_attrs[sub_k] = sub_v
            case _:
                raise ValueError(f"Unknown TAttribute type: {type(attr).__name__}")
    for acc_name, acc in attr_accs.items():
        new_attrs[acc_name] = acc.to_value()
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


def _prep_component_kwargs(
    callable_info: CallableInfo,
    attrs: AttributesDict,
    system: dict[str, object],
    kebab_to_snake: Callable[[str], str] = _kebab_to_snake,
):
    if callable_info.requires_positional:
        raise TypeError(
            "Component callables cannot have required positional arguments."
        )

    kwargs: AttributesDict = {}

    # Add all supported attributes
    for attr_name, attr_value in attrs.items():
        snake_name = kebab_to_snake(attr_name)
        if snake_name in callable_info.named_params or callable_info.kwargs:
            kwargs[snake_name] = attr_value

    for attr_name, attr_value in system.items():
        if attr_name in callable_info.named_params or callable_info.kwargs:
            kwargs[attr_name] = attr_value

    # Check to make sure we've fully satisfied the callable's requirements
    missing = callable_info.required_named_params - kwargs.keys()
    if missing:
        raise TypeError(
            f"Missing required parameters for component: {', '.join(missing)}"
        )

    return kwargs


def _invoke_component(
    attrs: AttributesDict,
    children: list[Node],  # TODO: why not TNode, though?
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

    kwargs = _prep_component_kwargs(
        callable_info, attrs, system={"children": tuple(children)}
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
            comment = format_template(comment_t)
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
