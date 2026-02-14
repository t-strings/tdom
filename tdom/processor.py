import sys
from typing import cast, Protocol
from collections.abc import Iterable, Sequence, Callable, Generator
from functools import lru_cache
from string.templatelib import Interpolation, Template
from dataclasses import dataclass

from markupsafe import Markup

from .callables import get_callable_info, CallableInfo
from .format import format_interpolation as base_format_interpolation
from .format import format_template
from .nodes import (
    Comment,
    DocumentType,
    Element,
    Fragment,
    Node,
    Text,
)
from .htmlspec import (
    VOID_ELEMENTS,
    CDATA_CONTENT_ELEMENTS,
    RCDATA_CONTENT_ELEMENTS,
)
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
from .protocols import HasHTMLDunder
from .escaping import (
    escape_html_script as default_escape_html_script,
    escape_html_style as default_escape_html_style,
    escape_html_text as default_escape_html_text,
    escape_html_comment as default_escape_html_comment,
)


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


def _expand_aria_attr(value: object) -> Iterable[HTMLAttribute]:
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


def _expand_data_attr(value: object) -> Iterable[Attribute]:
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


def _substitute_spread_attrs(value: object) -> Iterable[Attribute]:
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
    attrs: Sequence[TAttribute], interpolations: tuple[Interpolation, ...]
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
    attrs: Sequence[TAttribute], interpolations: tuple[Interpolation, ...]
) -> HTMLAttributesDict:
    """
    Substitute placeholders in attributes for HTML elements.

    This is the full pipeline: interpolation + HTML processing.
    """
    interpolated_attrs = _resolve_t_attrs(attrs, interpolations)
    return _resolve_html_attrs(interpolated_attrs)


def _flatten_nodes(nodes: Iterable[Node]) -> list[Node]:
    """Flatten a list of Nodes, expanding any Fragments."""
    flat: list[Node] = []
    for node in nodes:
        if isinstance(node, Fragment):
            flat.extend(node.children)
        else:
            flat.append(node)
    return flat


def _substitute_and_flatten_children(
    children: Iterable[TNode], interpolations: tuple[Interpolation, ...]
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
            return to_node(value)
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
            # they are zero-arg functions that return a value to be processed.
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
    system_kwargs: dict[str, object],
):
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

    for attr_name, attr_value in system_kwargs.items():
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
        callable_info, attrs, system_kwargs={"children": tuple(children)}
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


@dataclass
class EndTag:
    end_tag: str


def serialize_html_attrs(
    html_attrs: HTMLAttributesDict, escape: Callable = default_escape_html_text
) -> str:
    return "".join(
        (
            f' {k}="{escape(v)}"' if v is not None else f" {k}"
            for k, v in html_attrs.items()
        )
    )


type InterpolateInfo = tuple


type ProcessQueueItem = tuple[
    str | None, Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]
]


class InterpolatorProto(Protocol):
    def __call__(
        self,
        process_api: ProcessService,
        bf: list[str],
        last_parent_tag: str | None,
        template: Template,
        ip_info: InterpolateInfo,
    ) -> ProcessQueueItem | None:
        """
        Populates an interpolation or returns iterator to descend into.

        process_api
            The current process api, provides various helper methods.
        bf
            A list-like output buffer.
        last_parent_tag
            The last HTML tag known for this interpolation or None if unknown.
        template
            The "values" template that is being used to fulfill interpolations.
        ip_info
            The information provided in the structured template interpolation OR from another source,
            for example a value from a user provided iterator.

        Returns a process queue item when the main iteration loops needs to be paused and restarted to descend.
        """
        raise NotImplementedError


type InterpolateCommentInfo = tuple[str, Template]


def interpolate_comment(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    parent_tag, comment_t = cast(InterpolateCommentInfo, ip_info)
    assert parent_tag == "<!--"
    bf.append(
        process_api.escape_html_comment(
            resolve_text_without_recursion(template, parent_tag, comment_t),
            allow_markup=True,
        )
    )


type InterpolateAttrsInfo = tuple[str, Sequence[TAttribute]]


def interpolate_attrs(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    parent_tag, attrs = cast(InterpolateAttrsInfo, ip_info)
    resolved_attrs = process_api.resolve_attrs(attrs, template)
    attrs_str = serialize_html_attrs(_resolve_html_attrs(resolved_attrs))
    bf.append(attrs_str)


type InterpolateComponentInfo = tuple[str, Sequence[TAttribute], int, int | None, int]


class ComponentObjectProto(Protocol):
    def __call__(self) -> Template: ...


def interpolate_component(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    (parent_tag, attrs, start_i_index, end_i_index, body_start_s_index) = cast(
        InterpolateComponentInfo, ip_info
    )
    start_i = template.interpolations[start_i_index]
    component_callable = start_i.value
    if start_i_index != end_i_index and end_i_index is not None:
        # @TODO: We should do this during parsing.
        children_template = extract_embedded_template(
            template, body_start_s_index, end_i_index
        )
        if component_callable != template.interpolations[end_i_index].value:
            raise TypeError(
                "Component callable in start tag must match component callable in end tag."
            )
    else:
        children_template = t""

    system_kwargs = process_api.get_system(children=children_template)

    if not callable(component_callable):
        raise TypeError("Component callable must be callable.")

    kwargs = _prep_component_kwargs(
        get_callable_info(component_callable),
        _resolve_t_attrs(attrs, template.interpolations),
        system_kwargs=system_kwargs,
    )

    result_t = component_callable(**kwargs)
    if (
        result_t is not None
        and not isinstance(result_t, Template)
        and callable(result_t)
    ):
        component_obj = cast(ComponentObjectProto, result_t)
        result_t = component_obj()
    else:
        component_obj = None

    if isinstance(result_t, Template):
        if result_t.strings == ("",):
            # DO NOTHING
            return
        transformed_t = process_api.transform_api.transform_template(result_t)
        return process_api.make_process_queue_item(
            parent_tag, process_api.walk_template(bf, result_t, transformed_t)
        )
    elif result_t is None:
        # DO NOTHING
        return
    else:
        raise ValueError(f"Unknown component return value: {type(result_t)}")


type InterpolateRawTextsFromTemplateInfo = tuple[str, Template]


def interpolate_raw_texts_from_template(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    """
    Interpolate and join a template of raw texts together and escape them.

    @NOTE: This interpolator expects a Template.
    """
    parent_tag, content_t = cast(InterpolateRawTextsFromTemplateInfo, ip_info)
    content = resolve_text_without_recursion(template, parent_tag, content_t)
    if parent_tag == "script":
        bf.append(
            process_api.escape_html_script(
                parent_tag,
                content,
                allow_markup=True,
            )
        )
    elif parent_tag == "style":
        bf.append(
            process_api.escape_html_style(
                parent_tag,
                content,
                allow_markup=True,
            )
        )
    else:
        raise NotImplementedError(f"Parent tag {parent_tag} is not supported.")


type InterpolateEscapableRawTextsFromTemplateInfo = tuple[str, Template]


def interpolate_escapable_raw_texts_from_template(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    """
    Interpolate and join a template of escapable raw texts together and escape them.

    @NOTE: This interpolator expects a Template.
    """
    parent_tag, content_t = cast(InterpolateEscapableRawTextsFromTemplateInfo, ip_info)
    assert parent_tag == "title" or parent_tag == "textarea"
    bf.append(
        process_api.escape_html_text(
            resolve_text_without_recursion(template, parent_tag, content_t),
        )
    )


type InterpolateNormalTextInfo = tuple[str, int]


def interpolate_normal_text_from_interpolation(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    """
    Interpolate a single normal text either into structured content or an escaped string.

    @NOTE: This expects a SINGLE interpolation referenced via i_index.
    """
    parent_tag, ip_index = cast(InterpolateNormalTextInfo, ip_info)
    value = format_interpolation(template.interpolations[ip_index])
    return interpolate_normal_text_from_value(
        process_api, bf, last_parent_tag, template, (parent_tag, value)
    )


type InterpolateNormalTextValueInfo = tuple[str | None, object]


def interpolate_normal_text_from_value(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    """
    Resolve a single text value interpolated within a normal element.

    @NOTE: This could be a str(), None, Iterable, Template or HasHTMLDunder.
    """
    parent_tag, value = cast(InterpolateNormalTextValueInfo, ip_info)
    if parent_tag is None:
        parent_tag = last_parent_tag

    if isinstance(value, str):
        # @DESIGN: Objects with `__html__` must be wrapped with markupsafe.Markup.
        bf.append(process_api.escape_html_text(value))
    elif isinstance(value, Template):
        return process_api.make_process_queue_item(
            parent_tag,
            iter(
                process_api.walk_template(
                    bf, value, process_api.transform_api.transform_template(value)
                )
            ),
        )
    elif isinstance(value, Iterable):
        return process_api.make_process_queue_item(
            parent_tag,
            iter(
                (
                    interpolate_normal_text_from_value,
                    template,
                    (parent_tag, v),
                )
                for v in cast(Iterable, value)
            ),
        )
    elif value is None:
        # @DESIGN: Ignore None.
        return
    else:
        # @DESIGN: Everything that isn't an object we recognize is
        # coerced to a str() and emitted.
        bf.append(process_api.escape_html_text(str(value)))


type InterpolateDynamicTextsFromTemplateInfo = tuple[None, Template]


def interpolate_dynamic_texts_from_template(
    process_api: ProcessService,
    bf: list[str],
    last_parent_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> ProcessQueueItem | None:
    parent_tag, text_t = cast(InterpolateDynamicTextsFromTemplateInfo, ip_info)
    # Try to use the dynamic parent if possible.
    if parent_tag is None:
        parent_tag = last_parent_tag
    if parent_tag is None:
        raise NotImplementedError(
            "We cannot interpolate texts without knowing what tag they are contained in."
        )
    elif parent_tag in CDATA_CONTENT_ELEMENTS:
        return interpolate_raw_texts_from_template(
            process_api, bf, last_parent_tag, template, (parent_tag, text_t)
        )
    elif parent_tag in RCDATA_CONTENT_ELEMENTS:
        return interpolate_escapable_raw_texts_from_template(
            process_api, bf, last_parent_tag, template, (parent_tag, text_t)
        )
    else:
        return process_api.make_process_queue_item(
            parent_tag,
            iter(process_api.walk_dynamic_template(bf, template, text_t, parent_tag)),
        )


@dataclass(frozen=True)
class TransformService:
    """
    Turn a structure node tree into an optimized Template that can be quickly interpolated into a string.

    - Tag attributes with any interpolations are replaced with a single interpolation.
    - Component invocations are replaced with a single interpolation.
    - Runs of strings are consolidated around or in between interpolations.
      If there are no strings provided to build a proper template then empty strings are injected.
    """

    escape_html_text: Callable = default_escape_html_text

    slash_void: bool = False  # Apply a xhtml-style slash to void html elements.

    uppercase_doctype: bool = False  # DOCTYPE vs doctype

    def to_struct_node(self, template: Template) -> TNode:
        return TemplateParser.parse(template)

    def transform_template(self, template: Template) -> Template:
        """Transform the given template into a template for processing/writing."""
        struct_node = self.to_struct_node(template)
        return self.to_struct_template(struct_node)

    def to_struct_template(self, struct_node: TNode) -> Template:
        """Recombine stream of tokens from node trees into a new template."""
        return Template(*self.streamer(struct_node))

    def _stream_comment_interpolation(self, text_t: Template):
        info = ("<!--", text_t)
        return Interpolation(
            (interpolate_comment, info), "", None, "html_comment_template"
        )

    def _stream_attrs_interpolation(
        self, last_parent_tag: str | None, attrs: Sequence[TAttribute]
    ):
        info = (last_parent_tag, attrs)
        return Interpolation((interpolate_attrs, info), "", None, "html_attrs_seq")

    def _stream_component_interpolation(
        self, last_parent_tag, attrs, start_i_index, end_i_index
    ):
        # If the interpolation is at 1, then the opening string starts inside at least string 2 (+1)
        # but it can't start until after any dynamic attributes without our own tag
        # so we have to count past those.
        body_start_s_index = (
            start_i_index
            + 1
            + len([1 for attr in attrs if not isinstance(attr, TLiteralAttribute)])
        )
        info = (
            last_parent_tag,
            attrs,
            start_i_index,
            end_i_index,
            body_start_s_index,
        )
        return Interpolation((interpolate_component, info), "", None, "tdom_component")

    def _stream_raw_texts_interpolation(self, last_parent_tag: str, text_t: Template):
        info = (last_parent_tag, text_t)
        return Interpolation(
            (interpolate_raw_texts_from_template, info), "", None, "html_raw_texts"
        )

    def _stream_escapable_raw_texts_interpolation(
        self, last_parent_tag: str, text_t: Template
    ):
        info = (last_parent_tag, text_t)
        return Interpolation(
            (interpolate_escapable_raw_texts_from_template, info),
            "",
            None,
            "html_escapable_raw_texts",
        )

    def _stream_normal_text_interpolation(
        self, last_parent_tag: str, values_index: int
    ):
        info = (last_parent_tag, values_index)
        return Interpolation(
            (interpolate_normal_text_from_interpolation, info),
            "",
            None,
            "html_normal_text",
        )

    def _stream_dynamic_texts_interpolation(
        self, last_parent_tag: None, text_t: Template
    ):
        info = (last_parent_tag, text_t)
        return Interpolation(
            (interpolate_dynamic_texts_from_template, info),
            "",
            None,
            "html_dynamic_text",
        )

    def streamer(
        self, root: TNode, last_parent_tag: str | None = None
    ) -> Iterable[str | Interpolation]:
        """
        Stream template parts back out so they can be consolidated into a new HTML-aware template.
        """
        q: list[tuple[str | None, TNode | EndTag]] = [(last_parent_tag, root)]
        while q:
            last_parent_tag, tnode = q.pop()
            match tnode:
                case EndTag(end_tag):
                    yield end_tag
                case TDocumentType(text):
                    if self.uppercase_doctype:
                        yield f"<!DOCTYPE {text}>"
                    else:
                        yield f"<!doctype {text}>"
                case TComment(ref):
                    text_t = Template(
                        *[
                            part
                            if isinstance(part, str)
                            else Interpolation(part, "", None, "")
                            for part in iter(ref)
                        ]
                    )
                    yield "<!--"
                    yield self._stream_comment_interpolation(text_t)
                    yield "-->"
                case TFragment(children):
                    q.extend([(last_parent_tag, child) for child in reversed(children)])
                case TComponent(start_i_index, end_i_index, attrs, children):
                    yield self._stream_component_interpolation(
                        last_parent_tag, attrs, start_i_index, end_i_index
                    )
                case TElement(tag, attrs, children):
                    yield f"<{tag}"
                    if self.has_dynamic_attrs(attrs):
                        yield self._stream_attrs_interpolation(tag, attrs)
                    else:
                        yield serialize_html_attrs(
                            _resolve_html_attrs(
                                _resolve_t_attrs(attrs, interpolations=())
                            )
                        )
                    # @DESIGN: This is just a want to have.
                    if self.slash_void and tag in VOID_ELEMENTS:
                        yield " />"
                    else:
                        yield ">"
                    if tag not in VOID_ELEMENTS:
                        q.append((last_parent_tag, EndTag(f"</{tag}>")))
                        q.extend([(tag, child) for child in reversed(children)])
                case TText(ref):
                    text_t = Template(
                        *[
                            part
                            if isinstance(part, str)
                            else Interpolation(part, "", None, "")
                            for part in iter(ref)
                        ]
                    )
                    if ref.is_literal:
                        yield ref.strings[0]  # Trust literals.
                    elif last_parent_tag is None:
                        # We can't know how to handle this right now, so wait until write time and if
                        # we still cannot know then probably fail.
                        yield self._stream_dynamic_texts_interpolation(
                            last_parent_tag, text_t
                        )
                    elif last_parent_tag in CDATA_CONTENT_ELEMENTS:
                        # Must be handled all at once.
                        yield self._stream_raw_texts_interpolation(
                            last_parent_tag, text_t
                        )
                    elif last_parent_tag in RCDATA_CONTENT_ELEMENTS:
                        # We can handle all at once because there are no non-text children and everything must be string-ified.
                        yield self._stream_escapable_raw_texts_interpolation(
                            last_parent_tag, text_t
                        )
                    else:
                        # Flatten the template back out into the stream because each interpolation can
                        # be escaped as is and structured content can be injected between text anyways.
                        for part in text_t:
                            if isinstance(part, str):
                                yield part
                            else:
                                yield self._stream_normal_text_interpolation(
                                    last_parent_tag, part.value
                                )
                case _:
                    raise ValueError(f"Unrecognized tnode: {tnode}")

    def has_dynamic_attrs(self, attrs: Sequence[TAttribute]) -> bool:
        """
        Determine if any attributes with interpolations are in attrs sequence.

        This is mainly used to tell if we can pre-emptively serialize an
        element's attributes (or not).
        """
        for attr in attrs:
            if not isinstance(attr, TLiteralAttribute):
                return True
        return False


def resolve_text_without_recursion(
    template: Template, parent_tag: str, content_t: Template
) -> str | None:
    """
    Resolve the text in the given template without recursing into more structured text.

    This can be bypassed by interpolating an exact match with an object with `__html__()`.

    A non-exact match is not allowed because we cannot process escaping
    across the boundary between other content and the pass-through content.
    """
    # @TODO: We should use formatting but not in a way that
    # auto-interpolates structured values.
    if len(content_t.interpolations) == 1 and content_t.strings == ("", ""):
        i_index = cast(int, content_t.interpolations[0].value)
        value = template.interpolations[i_index].value
        if value is None:
            return None
        elif isinstance(value, str):
            # @DESIGN: Markup() must be used explicitly if you want __html__ supported.
            return value
        elif isinstance(value, (Template, Iterable)):
            raise ValueError(
                f"Recursive includes are not supported within {parent_tag}"
            )
        else:
            return str(value)
    else:
        text = []
        for part in content_t:
            if isinstance(part, str):
                if part:
                    text.append(part)
                continue
            value = template.interpolations[part.value].value
            if value is None:
                continue
            elif (
                type(value) is str
            ):  # type() check to avoid subclasses, probably something smarter here
                if value:
                    text.append(value)
            elif not isinstance(value, str) and isinstance(value, (Template, Iterable)):
                raise ValueError(
                    f"Recursive includes are not supported within {parent_tag}"
                )
            elif hasattr(value, "__html__"):
                raise ValueError(
                    f"Non-exact trusted interpolations are not supported within {parent_tag}"
                )
            else:
                value_str = str(value)
                if value_str:
                    text.append(value_str)
        if text:
            return "".join(text)
        else:
            return None


def determine_body_start_s_index(tcomp):
    """
    Calculate the strings index when the embedded template starts after a component start tag.

    This doesn't actually know or care if the component has a body it just
    counts past the dynamic (non-literal) attributes and returns the first strings index
    offset by interpolation index for the component callable itself.
    """
    return (
        tcomp.start_i_index
        + 1
        + len([1 for attr in tcomp.attrs if not isinstance(attr, TLiteralAttribute)])
    )


def extract_embedded_template(
    template: Template, body_start_s_index: int, end_i_index: int
) -> Template:
    """
    Extract the template parts exclusively from start tag to end tag.

    Note that interpolations INSIDE the start tag make this more complex
    than just "the `s_index` after the component callable's `i_index`".

    Example:
    ```python
    template = (
        t'<{comp} attr={attr}>'
            t'<div>{content} <span>{footer}</span></div>'
        t'</{comp}>'
    )
    assert extract_children_template(template, 2, 4) == (
        t'<div>{content} <span>{footer}</span></div>'
    )
    starttag = t'<{comp} attr={attr}>'
    endtag = t'</{comp}>'
    assert template == starttag + extract_children_template(template, 2, 4) + endtag
    ```
    @DESIGN: "There must be a better way."
    """
    # Copy the parts out of the containing template.
    index = body_start_s_index
    last_s_index = end_i_index
    parts = []
    while index <= last_s_index:
        parts.append(template.strings[index])
        if index != last_s_index:
            parts.append(template.interpolations[index])
        index += 1
    # Now trim the first part to the end of the opening tag.
    parts[0] = parts[0][parts[0].find(">") + 1 :]
    # Now trim the last part (could also be the first) to the start of the closing tag.
    parts[-1] = parts[-1][: parts[-1].rfind("<")]
    return Template(*parts)


@dataclass(frozen=True)
class ProcessService:
    transform_api: TransformService

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_script: Callable = default_escape_html_script

    escape_html_style: Callable = default_escape_html_style

    def get_system(self, **kwargs: object):
        return {**kwargs}

    def make_process_queue_item(
        self,
        last_parent_tag: str | None,
        it: Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]],
    ) -> ProcessQueueItem:
        """
        Coerce args into standard structure.

        This is almost only here for tracking and readability.
        """
        return (last_parent_tag, it)

    def process_template(
        self, template: Template, last_parent_tag: str | None = None
    ) -> str:
        """
        Process an HTML Template into a str and return it.

        The `last_parent_tag` is used for an HTML Template that contains
        interpolations without a definitive parent tag.  This creates a
        situation where interpolations cannot be resolved correctly.
        """
        return "".join(
            res for res in self.process_template_chunks(template, last_parent_tag)
        )

    def process_template_chunks(
        self, template: Template, last_parent_tag: str | None = None
    ) -> Generator[str]:
        """
        Process an HTML Template and yield intermittent str chunks until complete.

        SEE: process_template() for more information.
        """
        bf: list[str] = []
        q: list[ProcessQueueItem] = []
        q.append(
            (
                last_parent_tag,
                self.walk_template(
                    bf, template, self.transform_api.transform_template(template)
                ),
            )
        )
        while q:
            if bf:
                # Yield the buffer contents everytime we switch iterators,
                # either from exhaustion or traversal.
                yield "".join(bf)
                bf.clear()
            last_parent_tag, it = q.pop()
            for interpolator, template, ip_info in it:
                process_queue_item = interpolator(
                    self, bf, last_parent_tag, template, ip_info
                )
                if process_queue_item is not None:
                    #
                    # Pause the current iterator and push a new iterator on top of it.
                    #
                    q.append(self.make_process_queue_item(last_parent_tag, it))
                    q.append(process_queue_item)
                    break
        if bf:
            # Final yield in case we fell out of the `while q:`.
            yield "".join(bf)
            bf.clear()

    def resolve_attrs(
        self, attrs: Sequence[TAttribute], template: Template
    ) -> AttributesDict:
        return _resolve_t_attrs(attrs, template.interpolations)

    def walk_template(
        self, bf: list[str], original_t: Template, transformed_t: Template
    ) -> Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]:
        for part in transformed_t:
            if isinstance(part, str):
                bf.append(part)
            else:
                yield (part.value[0], original_t, part.value[1])

    def walk_dynamic_template(
        self,
        bf: list[str],
        original_t: Template,
        transformed_t: Template,
        parent_tag: str,
    ) -> Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]:
        """
        Walk a `Text()` template that we determined was OK during processing.

        This happens when the parent tag isn't resolvable at parse time and we
        have to discover it during processing.
        """
        for part in transformed_t:
            if isinstance(part, str):
                bf.append(part)
            else:
                yield (
                    interpolate_normal_text_from_interpolation,
                    original_t,
                    (parent_tag, part.value),
                )


def process_service_factory(transform_api_kwargs=None):
    return ProcessService(
        transform_api=TransformService(**(transform_api_kwargs or {}))
    )


def cached_process_service_factory(transform_api_kwargs=None):
    return ProcessService(
        transform_api=CachedTransformService(**(transform_api_kwargs or {}))
    )


#
# SHIM: This is here until we can find a way to make a configurable cache.
#
@dataclass(frozen=True)
class CachedTransformService(TransformService):
    @lru_cache(512)
    def _transform_template(self, cached_template: CachableTemplate) -> Template:
        return super().transform_template(cached_template.template)

    def transform_template(self, template: Template) -> Template:
        ct = CachableTemplate(template)
        return self._transform_template(ct)


_default_process_api = cached_process_service_factory(
    transform_api_kwargs=dict(slash_void=True, uppercase_doctype=True)
)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def to_html(template: Template, last_parent_tag: str | None = None) -> str:
    """Parse an HTML t-string, substitue values, and return a string of HTML."""
    return _default_process_api.process_template(template, last_parent_tag)


def to_node(template: Template) -> Node:
    """Parse an HTML t-string, substitue values, and return a tree of Nodes."""
    cachable = CachableTemplate(template)
    t_node = _parse_and_cache(cachable)
    return _resolve_t_node(t_node, template.interpolations)


# BWC: SHIM
html = to_node
