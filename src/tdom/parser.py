from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from string.templatelib import Template

from .exc import TemplatingError
from .htmlspec import VOID_ELEMENTS
from .parser_utils import (
    HTMLAttribute,
    ParserPositionTranslator,
    make_parser_pos_translator,
)
from .placeholders import (
    PlaceholderConfig,
    PlaceholderState,
)
from .placeholders import (
    make_placeholder_config as default_make_placeholder_config,
)
from .source import LinePosition, SourceReader
from .template_utils import PartPosition, TemplateRef, TemplateSpan
from .tnodes import (
    TagSourceInfo,
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
    TTree,
)


class ParsingError(TemplatingError):
    pass


class AttributeParsingError(ParsingError):
    pass


@dataclass(frozen=True, slots=True)
class OpenTagSourceInfo:
    """
    Retained tag information from the parsed source meant for error reporting.

    @NOTE: This is an temporary structure that will be finalized when the
    tag is closed.
    """

    starttag_span: TemplateSpan
    """Source span occupied by the start tag."""
    startend: bool
    """Was parsed as startend tag, ie. <tag />."""

    @property
    def starttag_pos(self) -> PartPosition:
        """Template part position where the start tag begins."""
        return self.starttag_span.start

    def close(self, endtag_pos: PartPosition | None = None) -> TagSourceInfo:
        return TagSourceInfo(
            starttag_span=self.starttag_span,
            startend=self.startend,
            endtag_pos=endtag_pos,
        )


@dataclass
class OpenTElement:
    tag: str
    attrs: tuple[TAttribute, ...]
    source_pos: PartPosition
    sinfo: OpenTagSourceInfo
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTFragment:
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTComponent:
    start_i_index: int
    children_start: PartPosition
    """Source position where the component's children start."""
    attrs: tuple[TAttribute, ...]
    source_pos: PartPosition
    sinfo: OpenTagSourceInfo
    # @NOTE: The `children` are discarded after parsing and are just used to
    # track template consistency.  If the component is processed and
    # returns its children template then that template will be
    # re-parsed (or pulled from the cache).
    children: list[TNode] = field(default_factory=list)


type OpenTag = OpenTElement | OpenTComponent


def configure_source_tracker(
    template: Template,
    make_placeholder_config: Callable[
        [], PlaceholderConfig
    ] = default_make_placeholder_config,
) -> SourceTracker:
    """
    Configure and return source tracker with its subcomponents.
    """
    config = make_placeholder_config()
    return SourceTracker(
        template=template,
        placeholders=PlaceholderState(config=config),
        parser_pos_translator=make_parser_pos_translator(template, config),
    )


@dataclass
class SourceTracker:
    """
    Iterator of template parts that adds placeholders to interpolations.
    """

    template: Template

    placeholders: PlaceholderState

    parser_pos_translator: ParserPositionTranslator
    """Translator from parser position to template part position."""

    index: int = -1
    """Unified template index that moves over interpolations and strings."""

    def __iter__(self):
        #
        # @NOTE: This iterator is only meant to be used once since we track
        # placeholders both by adding them and letting the user remove them
        # with calls to `remove_placeholders()`.
        return self

    def __next__(self):
        if self.index < 2 * len(self.template.strings) - 2:
            self.index += 1
            if self.index % 2 == 0:
                return self.template.strings[self.index // 2]
            else:
                return self.placeholders.add_placeholder((self.index - 1) // 2)
        else:
            raise StopIteration

    def remove_placeholders(self, text: str) -> TemplateRef:
        """
        Find tracked placeholders in text and mark them as found.

        @NOTE: Raises if any untracked placeholders are found.

        If you want to make a TemplateRef without changing state use
        `self.find_placeholders()`.
        """
        return self.placeholders.remove_placeholders(text)

    def find_placeholders(self, text: str) -> TemplateRef:
        """
        Find all placeholders without affecting tracking.
        """
        return self.placeholders.config.find_placeholders(text)

    def has_placeholders(self) -> bool:
        """
        Determine if known placeholders still remain.
        """
        return not self.placeholders.is_empty

    def translate_parser_pos(self, raw_parser_pos: LinePosition) -> PartPosition:
        """
        Translate a parser position to a part position within the template.
        """
        return self.parser_pos_translator.translate(raw_parser_pos)

    def translate_parser_span(
        self,
        raw_parser_start: LinePosition,
        raw_parser_length: int,
    ) -> TemplateSpan:
        """Translate a span in parser input into a span in the source template."""
        return self.parser_pos_translator.translate_span(
            raw_parser_start, raw_parser_length
        )


def make_error_helper(parser: TemplateParser) -> ParsingErrorHelper:
    """
    Factory that creates an error helper for the parser.

    @NOTE: This should only be used when an exception is already being
    generated.
    """
    return ParsingErrorHelper(
        reader=SourceReader(template=parser.get_source().template),
        sinfo_table=parser.sinfo_table.copy(),
    )


@dataclass()
class ParsingErrorHelper:
    """
    Helps the parser include extra info in parsing errors.

    This helper *should not* decide what error to raise.

    This helper *should* help to:
        - include possible reasons (did you forget to close a quote?)
        - include original template source (the start tag, etc.)
        - include position info (line #, etc.)
    """

    reader: SourceReader
    """ Used to read original template fragments and/or interpolation values. """

    sinfo_table: dict[PartPosition, TagSourceInfo]
    """ Source info mapping, copied from parser. """

    def make_mismatch_error(
        self,
        starttag_sinfo: OpenTagSourceInfo,
        endtag_ref: TemplateRef,
        endtag_pos: PartPosition,
    ) -> ParsingError:
        starttag_repr = self.reader.span_to_repr(starttag_sinfo.starttag_span)
        starttag_pos_msg = self.reader.make_template_pos_msg(
            starttag_sinfo.starttag_pos
        )
        endtag_repr = self.reader.ref_to_repr(endtag_ref)
        endtag_pos_msg = self.reader.make_template_pos_msg(endtag_pos)
        return ParsingError(
            f"Mismatched closing tag </{endtag_repr}> at {endtag_pos_msg} for {starttag_repr} at {starttag_pos_msg}."
        )

    def make_malformed_endtag_error(
        self, endtag_ref: TemplateRef, endtag_pos: PartPosition
    ) -> ParsingError:
        endtag_repr = self.reader.ref_to_repr(endtag_ref)
        endtag_pos_msg = self.reader.make_template_pos_msg(endtag_pos)
        return ParsingError(
            f"Component end tags must have exactly one interpolation, {endtag_repr} at {endtag_pos_msg}."
        )

    def make_unexpected_endtag_error(
        self, endtag_ref: TemplateRef, endtag_pos: PartPosition
    ) -> ParsingError:
        endtag_repr = self.reader.ref_to_repr(endtag_ref)
        endtag_pos_msg = self.reader.make_template_pos_msg(endtag_pos)
        return ParsingError(
            f"Unexpected closing tag </{endtag_repr}> with no open tag, {endtag_pos_msg}."
        )

    def make_unclosed_starttag_error(self, parent: OpenTag):
        starttag_repr = self.reader.span_to_repr(parent.sinfo.starttag_span)
        pos_msg = self.reader.make_template_pos_msg(parent.source_pos)
        return ParsingError(
            f"Invalid HTML structure: unclosed tag {starttag_repr} at {pos_msg}."
        )


class TemplateParser(HTMLParser):
    root: OpenTFragment
    stack: list[OpenTag]
    source: SourceTracker | None

    sinfo_table: dict[PartPosition, TagSourceInfo]
    """Tags with more source info than just a position are tracked in this mapping."""

    def __init__(self, *, convert_charrefs: bool = True):
        # This calls HTMLParser.reset() which we override to set up our state.
        super().__init__(convert_charrefs=convert_charrefs)

    # ------------------------------------------
    # Parse state helpers
    # ------------------------------------------

    def get_parent(self) -> OpenTag | OpenTFragment:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1] if self.stack else self.root

    def append_child(self, child: TNode) -> None:
        parent = self.get_parent()
        parent.children.append(child)

    def get_parser_pos(self) -> LinePosition:
        """
        Get the current position of the parser.

        @NOTE: This position is relative to text embedded with placeholders but
        can be translated back to the position within the original template.
        Since it *IS* relative to placeholders, ie. "SLOTS", this position is
        unique across a "family" of templates with the same structure.
        """
        line, offset = self.getpos()
        return LinePosition(line=line, offset=offset)

    def get_source_pos(self, parser_pos: LinePosition | None = None) -> PartPosition:
        """Translate the parser position into a part position in the source template."""
        source = self.get_source()
        return source.translate_parser_pos(
            self.get_parser_pos() if parser_pos is None else parser_pos
        )

    # ------------------------------------------
    # Attribute Helpers
    # ------------------------------------------

    def make_tattr(self, attr: HTMLAttribute) -> TAttribute:
        """Build a TAttribute from a raw attribute tuple."""
        source = self.get_source()

        name, value = attr

        name_ref = source.remove_placeholders(name)
        value_ref = source.remove_placeholders(value) if value is not None else None

        if name_ref.is_literal:
            if value_ref is None or value_ref.is_literal:
                return TLiteralAttribute(name=name, value=value)
            elif value_ref.is_singleton:
                return TInterpolatedAttribute(
                    name=name, value_i_index=value_ref.i_start
                )
            else:
                return TTemplatedAttribute(name=name, value_ref=value_ref)
        if value_ref is not None:
            raise AttributeParsingError(
                "Attribute names cannot contain interpolations if the value is also interpolated."
            )
        if not name_ref.is_singleton:
            raise AttributeParsingError(
                "Spread attributes must have exactly one interpolation in the name."
            )
        return TSpreadAttribute(i_index=name_ref.i_start)

    def make_tattrs(self, attrs: Sequence[HTMLAttribute]) -> tuple[TAttribute, ...]:
        """Build TAttributes from raw attribute tuples."""
        return tuple(self.make_tattr(attr) for attr in attrs)

    # ------------------------------------------
    # Tag Helpers
    # ------------------------------------------

    def make_open_tag(
        self,
        tag: str,
        attrs: Sequence[HTMLAttribute],
        startend: bool = False,
    ) -> OpenTag:
        """Build an OpenTag from a raw tag and attribute tuples."""
        source = self.get_source()

        tag_ref = source.remove_placeholders(tag)

        if tag_ref.is_literal:
            source_pos = self.get_source_pos()
            return OpenTElement(
                tag=tag,
                attrs=self.make_tattrs(attrs),
                sinfo=OpenTagSourceInfo(
                    starttag_span=self.get_starttag_span(),
                    startend=startend,
                ),
                source_pos=source_pos,
            )

        if not tag_ref.is_singleton:
            raise ParsingError(
                "Component element tags must have exactly one interpolation."
            )

        # HERE BE DRAGONS: the interpolation at i_index should be a
        # component callable. We do not check this in the parser, instead
        # relying on higher layers to validate types and render correctly.
        i_index = tag_ref.i_start

        # This must be called while handling the tag because HTMLParser retains
        # only the most recently parsed start tag text.
        starttag_span = self.get_starttag_span()
        source_pos = starttag_span.start

        return OpenTComponent(
            start_i_index=i_index,
            children_start=starttag_span.stop,
            attrs=self.make_tattrs(attrs),
            source_pos=source_pos,
            sinfo=OpenTagSourceInfo(
                starttag_span=starttag_span,
                startend=startend,
            ),
        )

    def finalize_tag(
        self,
        open_tag: OpenTag,
        endtag_i_index: int | None = None,
        endtag_pos: PartPosition | None = None,
    ) -> TNode:
        """Finalize an OpenTag into a TNode."""
        match open_tag:
            case OpenTElement(
                tag=tag,
                attrs=attrs,
                children=children,
                source_pos=source_pos,
                sinfo=sinfo,
            ):
                source_pos = (
                    open_tag.source_pos
                )  # Re-assignment for ty regression in 0.0.59
                self.sinfo_table[source_pos] = sinfo.close(endtag_pos=endtag_pos)
                return TElement(
                    tag=tag,
                    attrs=attrs,
                    children=tuple(children),
                    source_pos=source_pos,
                )
            case OpenTComponent(
                start_i_index=start_i_index,
                children_start=children_start,
                attrs=attrs,
                source_pos=source_pos,
                sinfo=sinfo,
            ):
                children_span = (
                    TemplateSpan(start=children_start, stop=endtag_pos)
                    if endtag_pos is not None
                    else None
                )
                self.sinfo_table[source_pos] = sinfo.close(endtag_pos=endtag_pos)
                return TComponent(
                    start_i_index=start_i_index,
                    end_i_index=endtag_i_index,
                    children_span=children_span,
                    attrs=attrs,
                    source_pos=source_pos,
                )

    def validate_end_tag(self, tag: str, open_tag: OpenTag) -> int | None:
        """Validate that closing tag matches open tag. Return component end index if applicable."""
        source = self.get_source()
        tag_ref = source.placeholders.remove_placeholders(tag)

        match open_tag:
            case OpenTElement():
                if tag_ref.is_singleton or (tag_ref.is_literal and tag != open_tag.tag):
                    raise make_error_helper(self).make_mismatch_error(
                        open_tag.sinfo, tag_ref, self.get_source_pos()
                    )
                elif not tag_ref.is_singleton and not tag_ref.is_literal:
                    raise make_error_helper(self).make_malformed_endtag_error(
                        tag_ref, self.get_source_pos()
                    )
                return None
            case OpenTComponent():
                if tag_ref.is_literal:
                    raise make_error_helper(self).make_mismatch_error(
                        open_tag.sinfo, tag_ref, self.get_source_pos()
                    )
                if not tag_ref.is_singleton:
                    raise make_error_helper(self).make_malformed_endtag_error(
                        tag_ref, self.get_source_pos()
                    )
                return tag_ref.i_start

    def get_starttag_span(self) -> TemplateSpan:
        """Return the source span occupied by the current start tag."""
        starttag_text = self.get_starttag_text()
        if starttag_text is None:
            raise AssertionError("Expected the parser to have starttag_text set.")

        source = self.get_source()
        line_pos = self.get_parser_pos()
        return source.translate_parser_span(line_pos, len(starttag_text))

    # ------------------------------------------
    # HTMLParser tag callbacks
    # ------------------------------------------

    def handle_starttag(self, tag: str, attrs: Sequence[HTMLAttribute]) -> None:
        open_tag = self.make_open_tag(tag, attrs)
        if isinstance(open_tag, OpenTElement) and open_tag.tag in VOID_ELEMENTS:
            final_tag = self.finalize_tag(open_tag)
            self.append_child(final_tag)
        else:
            self.stack.append(open_tag)

    def handle_startendtag(self, tag: str, attrs: Sequence[HTMLAttribute]) -> None:
        """Dispatch a self-closing tag, `<tag />` to specialized handlers."""
        open_tag = self.make_open_tag(tag, attrs, startend=True)
        final_tag = self.finalize_tag(open_tag)
        self.append_child(final_tag)

    def handle_endtag(self, tag: str) -> None:
        endtag_pos = self.get_source_pos()
        if not self.stack:
            source = self.get_source()
            endtag_ref = source.find_placeholders(tag)
            if endtag_ref.is_literal or endtag_ref.is_singleton:
                raise make_error_helper(self).make_unexpected_endtag_error(
                    endtag_ref, endtag_pos
                )
            else:
                raise make_error_helper(self).make_malformed_endtag_error(
                    endtag_ref, endtag_pos
                )
        open_tag = self.stack.pop()
        endtag_i_index = self.validate_end_tag(tag, open_tag)
        final_tag = self.finalize_tag(
            open_tag,
            endtag_i_index=endtag_i_index,
            endtag_pos=endtag_pos,
        )
        self.append_child(final_tag)

    # ------------------------------------------
    # HTMLParser other callbacks
    # ------------------------------------------

    def handle_data(self, data: str) -> None:
        source = self.get_source()
        ref = source.remove_placeholders(data)
        parent = self.get_parent()
        if parent.children and isinstance(parent.children[-1], TText):
            prior_text = parent.children[-1]
            parent.children[-1] = TText(
                ref=prior_text.ref.concat(ref),
                # Keep starting position of the prior text
                source_pos=prior_text.source_pos,
            )
        else:
            self.append_child(TText(ref=ref, source_pos=self.get_source_pos()))

    def handle_comment(self, data: str) -> None:
        source = self.get_source()
        ref = source.remove_placeholders(data)
        comment = TComment(ref=ref, source_pos=self.get_source_pos())
        self.append_child(comment)

    def handle_decl(self, decl: str) -> None:
        source = self.get_source()
        ref = source.remove_placeholders(decl)
        if not ref.is_literal:
            raise ParsingError("Interpolations are not allowed in declarations.")
        elif decl.upper().startswith("DOCTYPE "):
            doctype_content = decl[7:].strip()
            doctype = TDocumentType(doctype_content, source_pos=self.get_source_pos())
            self.append_child(doctype)
        else:
            raise ParsingError(
                "Only well formed DOCTYPE declarations are currently supported."
            )

    def reset(self):
        super().reset()
        self.root = OpenTFragment()
        self.stack = []
        self.source = None
        self.sinfo_table = {}

    def close(self) -> None:
        super().close()
        if self.stack:
            raise make_error_helper(self).make_unclosed_starttag_error(self.stack[-1])
        if self.source and self.source.has_placeholders():
            raise ParsingError("Some placeholders were never resolved.")

    # ------------------------------------------
    # Getting the parsed node tree
    # ------------------------------------------

    def get_tnode(self) -> TNode:
        """Get the Node tree parsed from the input HTML."""
        if len(self.root.children) > 1:
            # The parse structure results in multiple root elements, so we
            # return a Fragment to hold them all.
            return TFragment(children=tuple(self.root.children))
        elif len(self.root.children) == 1:
            # The parse structure results in a single root element, so we
            # return that element directly. This will be a non-Fragment Node.
            return self.root.children[0]
        else:
            # Special case: the parse structure is empty; we treat
            # this as an empty document fragment.
            # CONSIDER: or as an empty text node?
            return TFragment(children=())

    def get_ttree(self) -> TTree:
        return TTree(
            self.get_tnode(),
            sinfos=tuple(self.sinfo_table.values()),
        )

    # ------------------------------------------
    # Feeding and parsing
    # ------------------------------------------

    def get_source(self) -> SourceTracker:
        if self.source is None:
            raise AssertionError("Source has not been initialized.")
        return self.source

    def track_source(self, template: Template) -> SourceTracker:
        if self.source:
            raise AssertionError("Did you forget to call reset?")
        source = self.source = configure_source_tracker(template)
        return source

    def feed_template(self, template: Template) -> None:
        """Feed a Template's content to the parser."""
        for content in self.track_source(template):
            self.feed(content)

    @staticmethod
    def parse(t: Template) -> TTree:
        """
        Parse a Template containing valid HTML and substitutions and return
        a TTree representing its structure. This cachable structure can later
        be resolved against actual interpolation values to produce HTML.
        """
        parser = TemplateParser()
        parser.feed_template(t)
        parser.close()
        return parser.get_ttree()
