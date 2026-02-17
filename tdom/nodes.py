import sys
from dataclasses import dataclass, field
from functools import lru_cache
from string.templatelib import Template, Interpolation
from markupsafe import Markup
from collections.abc import Iterable, Sequence

from .escaping import (
    escape_html_comment,
    escape_html_script,
    escape_html_style,
    escape_html_text,
)
from .htmlspec import VOID_ELEMENTS, CONTENT_ELEMENTS
from .utils import CachableTemplate
from .processor import (
    format_interpolation,
    prep_component_kwargs,
    _resolve_html_attrs,
    _resolve_t_attrs,
    AttributesDict,
)
from .parser import (
    HTMLAttributesDict,
    TAttribute,
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TemplateParser,
    TFragment,
    TNode,
    TText,
)
from .protocols import HasHTMLDunder
from .format import format_template
from .callables import get_callable_info
from .template_utils import TemplateRef


@lru_cache(maxsize=0 if "pytest" in sys.modules else 512)
def _parse_and_cache(cachable: CachableTemplate) -> TNode:
    return TemplateParser.parse(cachable.template)


@dataclass(slots=True)
class Node:
    def __html__(self) -> str:
        """Return the HTML representation of the node."""
        # By default, just return the string representation
        return str(self)


@dataclass(slots=True)
class Text(Node):
    text: str  # which may be markupsafe.Markup in practice.

    def __str__(self) -> str:
        # Use markupsafe's escape to handle HTML escaping
        return escape_html_text(self.text)

    def __eq__(self, other: object) -> bool:
        # This is primarily of use for testing purposes. We only consider
        # two Text nodes equal if their string representations match.
        return isinstance(other, Text) and str(self) == str(other)


@dataclass(slots=True)
class Fragment(Node):
    children: list[Node] = field(default_factory=list)

    def __str__(self) -> str:
        return "".join(str(child) for child in self.children)


@dataclass(slots=True)
class Comment(Node):
    text: str

    def __str__(self) -> str:
        return f"<!--{escape_html_comment(self.text)}-->"


@dataclass(slots=True)
class DocumentType(Node):
    text: str = "html"

    def __str__(self) -> str:
        return f"<!DOCTYPE {self.text}>"


@dataclass(slots=True)
class Element(Node):
    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)

    def __post_init__(self):
        """Ensure all preconditions are met."""
        if not self.tag:
            raise ValueError("Element tag cannot be empty.")

        # Void elements cannot have children
        if self.is_void and self.children:
            raise ValueError(f"Void element <{self.tag}> cannot have children.")

    @property
    def is_void(self) -> bool:
        return self.tag in VOID_ELEMENTS

    @property
    def is_content(self) -> bool:
        return self.tag in CONTENT_ELEMENTS

    def _children_to_str(self):
        if not self.children:
            return ""
        if self.tag in ("script", "style"):
            chunks = []
            for child in self.children:
                if isinstance(child, Text):
                    chunks.append(child.text)
                else:
                    raise ValueError(
                        "Cannot serialize non-text content inside a script tag."
                    )
            raw_children_str = "".join(chunks)
            if self.tag == "script":
                return escape_html_script(raw_children_str)
            elif self.tag == "style":
                return escape_html_style(raw_children_str)
            else:
                raise ValueError("Unsupported tag for single-level bulk escaping.")
        else:
            return "".join(str(child) for child in self.children)

    def __str__(self) -> str:
        # We use markupsafe's escape to handle HTML escaping of attribute values
        # which means it's possible to mark them as safe if needed.
        attrs_str = "".join(
            f" {key}" if value is None else f' {key}="{escape_html_text(value)}"'
            for key, value in self.attrs.items()
        )
        if self.is_void:
            return f"<{self.tag}{attrs_str} />"
        if not self.children:
            return f"<{self.tag}{attrs_str}></{self.tag}>"
        children_str = self._children_to_str()
        return f"<{self.tag}{attrs_str}>{children_str}</{self.tag}>"


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

    kwargs = prep_component_kwargs(
        callable_info, attrs, system_kwargs={"children": tuple(children)}
    )

    result = value(**kwargs)
    return _node_from_value(result)


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
        for part in ref.resolve(interpolations)
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
            comment_t = ref.resolve(interpolations)
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
            if attrs:
                resolved_attrs = _resolve_attrs(attrs, interpolations)
            else:
                resolved_attrs = {}
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


def to_node(template: Template) -> Node:
    """Parse an HTML t-string, substitue values, and return a tree of Nodes."""
    cachable = CachableTemplate(template)
    t_node = _parse_and_cache(cachable)
    return _resolve_t_node(t_node, template.interpolations)
