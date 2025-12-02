from dataclasses import dataclass, field
from string.templatelib import Template

from .escaping import (
    escape_html_comment,
    escape_html_script,
    escape_html_style,
    escape_html_text,
)


# See https://developer.mozilla.org/en-US/docs/Glossary/Void_element
VOID_ELEMENTS = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)


CDATA_CONTENT_ELEMENTS = frozenset(["script", "style"])
RCDATA_CONTENT_ELEMENTS = frozenset(["textarea", "title"])
CONTENT_ELEMENTS = CDATA_CONTENT_ELEMENTS | RCDATA_CONTENT_ELEMENTS

# FUTURE: add a pretty-printer to nodes for debugging
# FUTURE: make nodes frozen (and have the parser work with mutable builders)


def to_template_repr(template):
    """
    Convert a template to a comparable representation.

    This is mostly for testing because Templates/Interpolations are not comparable.
    """
    parts = []
    for index, s in enumerate(template.strings):
        parts.append(s)
        if index < len(template.strings) - 1:
            ip = template.interpolations[index]
            parts.append((ip.value, ip.expression, ip.conversion, ip.format_spec))
    return tuple(parts)


@dataclass
class ComponentInfo:
    starttag_interpolation_index: int
    endtag_interpolation_index: int = -1
    strings_slice_begin: int = 0
    strings_slice_end: int = 0


@dataclass
class TNode:
    def __str__(self) -> str:
        raise NotImplementedError("Cannot serialize dynamic nodes.")

    def __html__(self) -> str:
        raise NotImplementedError("Cannot serialize dynamic nodes.")


@dataclass
class TElement(TNode):
    tag: str
    attrs: tuple[tuple[str | int, ...], ...]
    children: list = field(default_factory=list)
    component_info: ComponentInfo | None = None

    def to_comparable(self) -> tuple:
        """
        Generate a tuple of our state to compare to another Element.

        """
        return (
            self.tag,
            self.attrs,
            self.children,
            self.component_info,
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, TElement)
            and self.to_comparable() == other.to_comparable()
        )


@dataclass
class TFragment(TNode):
    children: list = field(default_factory=list)


@dataclass
class TText:
    text_t: Template

    def __eq__(self, other: object) -> bool:
        # This is primarily of use for testing purposes. We only consider
        # two Text nodes equal if their string representations match.
        return isinstance(other, TText) and to_template_repr(
            self.text_t
        ) == to_template_repr(other.text_t)


@dataclass
class TComment:
    text_t: Template

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TComment) and to_template_repr(
            self.text_t
        ) == to_template_repr(other.text_t)


@dataclass(slots=True)
class Node(TNode):
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
