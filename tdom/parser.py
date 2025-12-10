import typing as t
from dataclasses import dataclass, field
from html.parser import HTMLParser
from string.templatelib import Template

from .nodes import (
    CONTENT_ELEMENTS,
    VOID_ELEMENTS,
)
from .placeholders import PlaceholderState, TemplateRef

# ------------------------------------------------------
# Semantic attribute types
# ------------------------------------------------------


@dataclass(slots=True)
class TLiteralAttribute:
    name: str
    value: str | None


@dataclass(slots=True)
class TInterpolatedAttribute:
    name: str
    value_i_index: int


@dataclass(slots=True)
class TTemplatedAttribute:
    name: str
    value_ref: TemplateRef


@dataclass(slots=True)
class TSpreadAttribute:
    i_index: int


type TAttribute = (
    TLiteralAttribute | TTemplatedAttribute | TInterpolatedAttribute | TSpreadAttribute
)


# ------------------------------------------------------
# Semantic node types
# ------------------------------------------------------


@dataclass(slots=True)
class TNode:
    def __html__(self) -> str:
        raise NotImplementedError("Cannot render TNode to HTML directly.")

    def __str__(self) -> str:
        raise NotImplementedError("Cannot render TNode to string directly.")


@dataclass(slots=True)
class TText(TNode):
    ref: TemplateRef

    @classmethod
    def empty(cls) -> t.Self:
        return cls(TemplateRef.empty())

    @classmethod
    def static(cls, text: str) -> t.Self:
        return cls(TemplateRef.static(text))


@dataclass(slots=True)
class TComment(TNode):
    ref: TemplateRef

    @classmethod
    def static(cls, text: str) -> t.Self:
        return cls(TemplateRef.static(text))


@dataclass(slots=True)
class TDocumentType(TNode):
    text: str


@dataclass(slots=True)
class TFragment(TNode):
    children: list[TNode]


@dataclass(slots=True)
class TElement(TNode):
    tag: str
    attrs: list[TAttribute] = field(default_factory=list)
    children: list[TNode] = field(default_factory=list)


@dataclass(slots=True)
class TComponent(TNode):
    start_i_index: int
    """The interpolation index for the component's starting tag name."""

    end_i_index: int | None = None
    """The interpolation index for the component's ending tag name, if any."""

    attrs: list[TAttribute] = field(default_factory=list)
    children: list[TNode] = field(default_factory=list)


type TTag = TElement | TComponent


# ------------------------------------------------------
# HTML parser
# ------------------------------------------------------


class TemplateParser(HTMLParser):
    root: TFragment
    stack: list[TTag]
    placeholder_state: PlaceholderState

    def __init__(self):
        super().__init__()
        self.root = TFragment(children=[])
        self.stack = []
        self.placeholder_state = PlaceholderState()

    def _make_attribute(self, a: tuple[str, str | None]) -> TAttribute:
        """Build a TAttribute from a raw attribute tuple."""

        name, value = a
        name_ref = self.placeholder_state.remove_placeholders(name)
        value_ref = (
            self.placeholder_state.remove_placeholders(value)
            if value is not None
            else None
        )

        # CONSIDER: allow templating a name? A name *and* a value? I mean,
        # why not?

        if name_ref.is_static:
            if value_ref is None or value_ref.is_static:
                return TLiteralAttribute(name=name, value=value)
            elif value_ref.is_singleton:
                return TInterpolatedAttribute(
                    name=name, value_i_index=value_ref.i_indexes[0]
                )
            else:
                return TTemplatedAttribute(name=name, value_ref=value_ref)
        if value_ref is not None:
            raise ValueError(
                "Attribute names cannot contain interpolations if the value is also interpolated."
            )
        if not name_ref.is_singleton:
            raise ValueError(
                "Spread attributes must have exactly one interpolation in the name."
            )
        return TSpreadAttribute(i_index=name_ref.i_indexes[0])

    def _make_tag(self, tag: str, attrs: t.Sequence[tuple[str, str | None]]) -> TTag:
        """Build a TElement from a raw tag and attribute list."""
        tattrs = [self._make_attribute(a) for a in attrs]
        tag_ref = self.placeholder_state.remove_placeholders(tag)
        if tag_ref.is_static:
            return TElement(tag=tag, attrs=tattrs, children=[])
        if not tag_ref.is_singleton:
            raise ValueError(
                "Component element tags must have exactly one interpolation."
            )
        return TComponent(
            start_i_index=tag_ref.i_indexes[0],
            attrs=tattrs,
            children=[],
        )

    def handle_starttag(
        self, tag: str, attrs: t.Sequence[tuple[str, str | None]]
    ) -> None:
        node = self._make_tag(tag, attrs)
        if tag in VOID_ELEMENTS:
            self.append_element_child(node)
        else:
            self.stack.append(node)

    def handle_startendtag(
        self, tag: str, attrs: t.Sequence[tuple[str, str | None]]
    ) -> None:
        node = self._make_tag(tag, attrs)
        self.append_element_child(node)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            raise ValueError(f"Unexpected closing tag </{tag}> with no open element.")

        element = self.stack.pop()
        if isinstance(element, TElement):
            if element.tag != tag:
                raise ValueError(
                    f"Mismatched closing tag </{tag}> for <{element.tag}>."
                )
        else:
            # HERE BE DRAGONS:
            #
            # Ignore the end tag in parsing; if it doesn't match, we'll
            # catch later, when we resolve and render the TComponent.
            #
            # This allows us to avoid caching based on interpolation values
            # at a higher layer, which we think is a good trade-off for now.
            tag_ref = self.placeholder_state.remove_placeholders(tag)
            if not tag_ref.is_singleton:
                raise ValueError(
                    "Component element closing tags must have exactly one interpolation."
                )
            element.end_i_index = tag_ref.i_indexes[0]

        self.append_element_child(element)

    def handle_data(self, data: str) -> None:
        ref = self.placeholder_state.remove_placeholders(data)
        text = TText(ref)
        self.append_child(text)

    def handle_comment(self, data: str) -> None:
        ref = self.placeholder_state.remove_placeholders(data)
        comment = TComment(ref)
        self.append_child(comment)

    def handle_decl(self, decl: str) -> None:
        ref = self.placeholder_state.remove_placeholders(decl)
        if not ref.is_static:
            raise ValueError("Interpolations are not allowed in declarations.")
        if not decl.upper().startswith("DOCTYPE"):
            raise NotImplementedError(
                "Only DOCTYPE declarations are currently supported."
            )
        doctype_content = decl[7:].strip()
        doctype = TDocumentType(doctype_content)
        self.append_child(doctype)

    def in_content_element(self) -> bool:
        """Return True if the current context is within a content element."""
        open_element = self.get_open_element()
        return (
            isinstance(open_element, TElement) and open_element.tag in CONTENT_ELEMENTS
        )

    def get_parent(self) -> TFragment | TTag:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1] if self.stack else self.root

    def get_open_element(self) -> TTag | None:
        """Return the currently open Element, if any."""
        return self.stack[-1] if self.stack else None

    def append_element_child(self, child: TTag) -> None:
        parent = self.get_parent()
        # node: TElement | TFragment = child
        # # Special case: if the element is a Fragment, convert it to a Fragment node.
        # if child.tag == _FRAGMENT_TAG:
        #     assert not child.attrs, (
        #         "Fragment elements should never be able to have attributes."
        #     )
        #     node = Fragment(children=child.children)
        parent.children.append(child)

    def append_child(self, child: TFragment | TText | TComment | TDocumentType) -> None:
        parent = self.get_parent()
        parent.children.append(child)

    def close(self) -> None:
        if self.stack:
            raise ValueError("Invalid HTML structure: unclosed tags remain.")
        super().close()

    def get_tnode(self) -> TNode:
        """Get the Node tree parsed from the input HTML."""
        assert not self.stack, "Did you forget to call close()?"
        if len(self.root.children) > 1:
            # The parse structure results in multiple root elements, so we
            # return a Fragment to hold them all.
            return self.root
        elif len(self.root.children) == 1:
            # The parse structure results in a single root element, so we
            # return that element directly. This will be a non-Fragment Node.
            return self.root.children[0]
        else:
            # Special case: the parse structure is empty; we treat
            # this as an empty Text Node.
            return TText.empty()

    def feed_str(self, s: str) -> None:
        """Feed a string part of a Template to the parser."""
        self.feed(s)

    def feed_interpolation(self, index: int) -> None:
        placeholder = self.placeholder_state.add_placeholder(index)
        self.feed(placeholder)

    def feed_template(self, t: Template) -> None:
        """Feed a Template's content to the parser."""
        index = 0
        for part in t:
            if isinstance(part, str):
                self.feed_str(part)
            else:
                self.feed_interpolation(index)
                index += 1

    @staticmethod
    def parse(t: Template) -> TNode:
        """
        Parse a Template containing valid HTML and substitutions and return
        a TNode tree representing its structure. This cachable structure can later
        be resolved against actual interpolation values to produce a Node tree.
        """
        parser = TemplateParser()
        parser.feed_template(t)
        parser.close()
        return parser.get_tnode()
