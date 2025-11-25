from dataclasses import dataclass, field

from .escaping import escape_html_comment, escape_html_script, escape_html_style, escape_html_text


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
        return escape(self.text)

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
        return f"<!--{self.text}-->"


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

    def __str__(self) -> str:
        # We use markupsafe's escape to handle HTML escaping of attribute values
        # which means it's possible to mark them as safe if needed.
        attrs_str = "".join(
            f" {key}" if value is None else f' {key}="{escape(value)}"'
            for key, value in self.attrs.items()
        )
        if self.is_void:
            return f"<{self.tag}{attrs_str} />"
        if not self.children:
            return f"<{self.tag}{attrs_str}></{self.tag}>"
        children_str = "".join(str(child) for child in self.children)
        return f"<{self.tag}{attrs_str}>{children_str}</{self.tag}>"
