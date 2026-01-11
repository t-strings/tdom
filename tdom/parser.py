import typing as t
from dataclasses import dataclass, field
from html.parser import HTMLParser
from string.templatelib import Interpolation, Template

from .nodes import VOID_ELEMENTS
from .placeholders import PlaceholderState
from .tnodes import (
    TAttribute,
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TFragment,
    TInterpolatedAttribute,
    TLiteralAttribute,
    TNode,
    TSpreadAttribute,
    TTemplatedAttribute,
    TText,
)
from .template_utils import combine_template_refs


type HTMLAttribute = tuple[str, str | None]
type HTMLAttributesDict = dict[str, str | None]


@dataclass
class OpenTElement:
    tag: str
    attrs: tuple[TAttribute, ...]
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTFragment:
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTComponent:
    start_i_index: int
    attrs: tuple[TAttribute, ...]
    children: list[TNode] = field(default_factory=list)


type OpenTag = OpenTElement | OpenTFragment | OpenTComponent


@dataclass
class SourceTracker:
    """Tracks source locations within a Template for error reporting."""

    # TODO: write utilities to generate complete error messages, with the
    # template itself in context and the relevant line/column underlined/etc.

    template: Template
    i_index: int = -1  # The current interpolation index.

    @property
    def interpolations(self) -> tuple[Interpolation, ...]:
        return self.template.interpolations

    def advance_interpolation(self) -> int:
        """Call before processing an interpolation to move to the next one."""
        self.i_index += 1
        return self.i_index

    def get_expression(
        self, i_index: int, fallback_prefix: str = "interpolation"
    ) -> str:
        """
        Resolve an interpolation index to its original expression for error messages.
        Falls back to a synthetic expression if the original is empty.
        """
        ip = self.interpolations[i_index]
        return ip.expression if ip.expression else f"{{{fallback_prefix}-{i_index}}}"

    def format_starttag(self, i_index: int) -> str:
        """Format a component start tag for error messages."""
        return self.get_expression(i_index, fallback_prefix="component-starttag")


class TemplateParser(HTMLParser):
    root: OpenTFragment
    stack: list[OpenTag]
    placeholders: PlaceholderState
    source: SourceTracker | None

    def __init__(self, *, convert_charrefs: bool = True):
        # This calls HTMLParser.reset() which we override to set up our state.
        super().__init__(convert_charrefs=convert_charrefs)

    # ------------------------------------------
    # Parse state helpers
    # ------------------------------------------

    def get_parent(self) -> OpenTag:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1] if self.stack else self.root

    def append_child(self, child: TNode) -> None:
        parent = self.get_parent()
        parent.children.append(child)

    # ------------------------------------------
    # Attribute Helpers
    # ------------------------------------------

    def make_tattr(self, attr: HTMLAttribute) -> TAttribute:
        """Build a TAttribute from a raw attribute tuple."""

        name, value = attr
        name_ref = self.placeholders.remove_placeholders(name)
        value_ref = (
            self.placeholders.remove_placeholders(value) if value is not None else None
        )

        if name_ref.is_literal:
            if value_ref is None or value_ref.is_literal:
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

    def make_tattrs(self, attrs: t.Sequence[HTMLAttribute]) -> tuple[TAttribute, ...]:
        """Build TAttributes from raw attribute tuples."""
        return tuple(self.make_tattr(attr) for attr in attrs)

    # ------------------------------------------
    # Tag Helpers
    # ------------------------------------------

    def make_open_tag(self, tag: str, attrs: t.Sequence[HTMLAttribute]) -> OpenTag:
        """Build an OpenTag from a raw tag and attribute tuples."""
        tag_ref = self.placeholders.remove_placeholders(tag)

        if tag_ref.is_literal:
            return OpenTElement(tag=tag, attrs=self.make_tattrs(attrs))

        if not tag_ref.is_singleton:
            raise ValueError(
                "Component element tags must have exactly one interpolation."
            )

        # HERE BE DRAGONS: the interpolation at i_index should be a
        # component callable. We do not check this in the parser, instead
        # relying on higher layers to validate types and render correctly.
        i_index = tag_ref.i_indexes[0]
        return OpenTComponent(
            start_i_index=i_index,
            attrs=self.make_tattrs(attrs),
        )

    def finalize_tag(
        self, open_tag: OpenTag, endtag_i_index: int | None = None
    ) -> TNode:
        """Finalize an OpenTag into a TNode."""
        match open_tag:
            case OpenTElement(tag=tag, attrs=attrs, children=children):
                return TElement(tag=tag, attrs=attrs, children=tuple(children))
            case OpenTFragment(children=children):
                return TFragment(children=tuple(children))
            case OpenTComponent(
                start_i_index=start_i_index,
                attrs=attrs,
                children=children,
            ):
                return TComponent(
                    start_i_index=start_i_index,
                    end_i_index=endtag_i_index,
                    attrs=attrs,
                    children=tuple(children),
                )

    def validate_end_tag(self, tag: str, open_tag: OpenTag) -> int | None:
        """Validate that closing tag matches open tag. Return component end index if applicable."""
        assert self.source, "Parser source tracker not initialized."
        tag_ref = self.placeholders.remove_placeholders(tag)

        match open_tag:
            case OpenTElement():
                if not tag_ref.is_literal:
                    raise ValueError(
                        f"Component closing tag found for element <{open_tag.tag}>."
                    )
                if tag != open_tag.tag:
                    raise ValueError(
                        f"Mismatched closing tag </{tag}> for element <{open_tag.tag}>."
                    )
                return None

            case OpenTFragment():
                raise NotImplementedError("We do not support anonymous fragments.")

            case OpenTComponent(start_i_index=start_i_index):
                if tag_ref.is_literal:
                    raise ValueError(
                        f"Mismatched closing tag </{tag}> for component starting at {self.source.format_starttag(start_i_index)}."
                    )
                if not tag_ref.is_singleton:
                    raise ValueError(
                        "Component end tags must have exactly one interpolation."
                    )
                # HERE BE DRAGONS: the interpolation at end_i_index shuld be a
                # component callable that matches the start tag. We do not check
                # any of this in the parser, instead relying on higher layers.
                return tag_ref.i_indexes[0]

    # ------------------------------------------
    # HTMLParser tag callbacks
    # ------------------------------------------

    def handle_starttag(self, tag: str, attrs: t.Sequence[HTMLAttribute]) -> None:
        open_tag = self.make_open_tag(tag, attrs)
        if isinstance(open_tag, OpenTElement) and open_tag.tag in VOID_ELEMENTS:
            final_tag = self.finalize_tag(open_tag)
            self.append_child(final_tag)
        else:
            self.stack.append(open_tag)

    def handle_startendtag(self, tag: str, attrs: t.Sequence[HTMLAttribute]) -> None:
        """Dispatch a self-closing tag, `<tag />` to specialized handlers."""
        open_tag = self.make_open_tag(tag, attrs)
        final_tag = self.finalize_tag(open_tag)
        self.append_child(final_tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            raise ValueError(f"Unexpected closing tag </{tag}> with no open tag.")

        open_tag = self.stack.pop()
        endtag_i_index = self.validate_end_tag(tag, open_tag)
        final_tag = self.finalize_tag(open_tag, endtag_i_index)
        self.append_child(final_tag)

    # ------------------------------------------
    # HTMLParser other callbacks
    # ------------------------------------------

    def handle_data(self, data: str) -> None:
        ref = self.placeholders.remove_placeholders(data)
        parent = self.get_parent()
        if parent.children and isinstance(parent.children[-1], TText):
            parent.children[-1] = TText(
                ref=combine_template_refs(parent.children[-1].ref, ref)
            )
        else:
            self.append_child(TText(ref=ref))

    def handle_comment(self, data: str) -> None:
        ref = self.placeholders.remove_placeholders(data)
        comment = TComment(ref)
        self.append_child(comment)

    def handle_decl(self, decl: str) -> None:
        ref = self.placeholders.remove_placeholders(decl)
        if not ref.is_literal:
            raise ValueError("Interpolations are not allowed in declarations.")
        elif decl.upper().startswith("DOCTYPE "):
            doctype_content = decl[7:].strip()
            doctype = TDocumentType(doctype_content)
            self.append_child(doctype)
        else:
            raise NotImplementedError(
                "Only well formed DOCTYPE declarations are currently supported."
            )

    def reset(self):
        super().reset()
        self.root = OpenTFragment()
        self.stack = []
        self.placeholders = PlaceholderState()
        self.source = None

    def close(self) -> None:
        if self.stack:
            raise ValueError("Invalid HTML structure: unclosed tags remain.")
        if not self.placeholders.is_empty:
            raise ValueError("Some placeholders were never resolved.")
        super().close()

    # ------------------------------------------
    # Getting the parsed node tree
    # ------------------------------------------

    def get_tnode(self) -> TNode:
        """Get the Node tree parsed from the input HTML."""
        # TODO: consider always returning a TTag?
        if len(self.root.children) > 1:
            # The parse structure results in multiple root elements, so we
            # return a Fragment to hold them all.
            return self.finalize_tag(self.root)
        elif len(self.root.children) == 1:
            # The parse structure results in a single root element, so we
            # return that element directly. This will be a non-Fragment Node.
            return self.root.children[0]
        else:
            # Special case: the parse structure is empty; we treat
            # this as an empty document fragment.
            # CONSIDER: or as an empty text node?
            return self.finalize_tag(self.root)

    # ------------------------------------------
    # Feeding and parsing
    # ------------------------------------------

    def feed_str(self, s: str) -> None:
        """Feed a string part of a Template to the parser."""
        self.feed(s)

    def feed_interpolation(self, index: int) -> None:
        placeholder = self.placeholders.add_placeholder(index)
        self.feed(placeholder)

    def feed_template(self, template: Template) -> None:
        """Feed a Template's content to the parser."""
        assert self.source is None, "Did you forget to call reset?"
        self.source = SourceTracker(template)
        for i_index in range(len(template.interpolations)):
            self.feed_str(template.strings[i_index])
            self.source.advance_interpolation()
            self.feed_interpolation(i_index)
        self.feed_str(template.strings[-1])

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
