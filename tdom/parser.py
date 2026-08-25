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


class ParsingAssertionError(ParsingError):
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
    source_pos: PartPosition | None = None
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


type OpenTag = OpenTElement | OpenTFragment | OpenTComponent


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

    def get_reader(self) -> SourceReader:
        return SourceReader(template=self.template)

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

    def get_expression(
        self, i_index: int, fallback_prefix: str = "interpolation"
    ) -> str:
        """
        Resolve an interpolation index to its original expression for error messages.
        Falls back to a synthetic expression if the original is empty.
        """
        ip = self.template.interpolations[i_index]
        return ip.expression if ip.expression else f"{{{fallback_prefix}-{i_index}}}"

    def format_starttag(self, i_index: int) -> str:
        """Format a component start tag for error messages."""
        return self.get_expression(i_index, fallback_prefix="component-starttag")


class TemplateParser(HTMLParser):
    root: OpenTFragment
    stack: list[OpenTag]
    source: SourceTracker | None

    tcomponent_children: dict[TComponent, list[TNode]]
    "List of children for each finished tcomponent, stored at closing. "

    sinfo_table: dict[PartPosition, TagSourceInfo]
    """Tags with more source info than just a position are tracked in this mapping."""

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
            case OpenTFragment(children=children, source_pos=source_pos):
                return TFragment(children=tuple(children), source_pos=source_pos)
            case OpenTComponent(
                start_i_index=start_i_index,
                children_start=children_start,
                attrs=attrs,
                source_pos=source_pos,
                sinfo=sinfo,
                children=children,
            ):
                children_span = (
                    TemplateSpan(start=children_start, stop=endtag_pos)
                    if endtag_pos is not None
                    else None
                )
                self.sinfo_table[source_pos] = sinfo.close(endtag_pos=endtag_pos)
                tnode = TComponent(
                    start_i_index=start_i_index,
                    end_i_index=endtag_i_index,
                    children_span=children_span,
                    attrs=attrs,
                    source_pos=source_pos,
                )
                # Save children for introspection after some parsing errors otherwise
                # they are discarded since we extract the children_span in the processor
                # for the components.
                self.tcomponent_children[tnode] = children
                return tnode

    def make_mismatch_error(
        self,
        starttag_sinfo: OpenTagSourceInfo,
        starttag_attrs: tuple[TAttribute, ...],
        endtag_ref: TemplateRef,
        endtag_pos: PartPosition,
    ) -> ParsingError:
        reader = self.get_source().get_reader()
        starttag_repr = reader.span_to_repr(starttag_sinfo.starttag_span)
        starttag_pos_msg = reader.make_template_pos_msg(starttag_sinfo.starttag_pos)
        endtag_repr = reader.ref_to_repr(endtag_ref)
        endtag_pos_msg = reader.make_template_pos_msg(endtag_pos)
        e = ParsingError(
            f"Mismatched closing tag </{endtag_repr}> at {endtag_pos_msg} for {starttag_repr} at {starttag_pos_msg}."
        )
        if self.has_ambiguous_forward_slash(starttag_sinfo, starttag_attrs):
            e.add_note(
                f'Did you mean to quote the last attribute or put a space before "/>" for "{starttag_repr}" at {starttag_pos_msg}?'
            )
        return e

    def make_invalid_endtag_error(
        self, endtag_ref: TemplateRef, endtag_pos: PartPosition
    ) -> ParsingError:
        reader = self.get_source().get_reader()
        endtag_repr = reader.ref_to_repr(endtag_ref)
        endtag_pos_msg = reader.make_template_pos_msg(endtag_pos)
        raise ParsingError(
            f"Component end tags must have exactly one interpolation, {endtag_repr} at {endtag_pos_msg}."
        )

    def validate_end_tag(self, tag: str, open_tag: OpenTag) -> int | None:
        """Validate that closing tag matches open tag. Return component end index if applicable."""
        source = self.get_source()
        tag_ref = source.placeholders.remove_placeholders(tag)

        match open_tag:
            case OpenTElement():
                if tag_ref.is_singleton or (tag_ref.is_literal and tag != open_tag.tag):
                    raise self.make_mismatch_error(
                        open_tag.sinfo, open_tag.attrs, tag_ref, self.get_source_pos()
                    )
                elif not tag_ref.is_singleton and not tag_ref.is_literal:
                    raise self.make_invalid_endtag_error(tag_ref, self.get_source_pos())
                return None
            case OpenTFragment():
                raise ParsingAssertionError("We do not support anonymous fragments.")
            case OpenTComponent():
                if tag_ref.is_literal:
                    raise self.make_mismatch_error(
                        open_tag.sinfo, open_tag.attrs, tag_ref, self.get_source_pos()
                    )
                if not tag_ref.is_singleton:
                    raise self.make_invalid_endtag_error(tag_ref, self.get_source_pos())
                return tag_ref.i_start

    def get_starttag_span(self) -> TemplateSpan:
        """Return the source span occupied by the current start tag."""
        starttag_text = self.get_starttag_text()
        if starttag_text is None:
            raise ParsingAssertionError(
                "Expected the parser to have starttag_text set."
            )

        source = self.get_source()
        line_pos = self.get_parser_pos()
        return source.translate_parser_span(line_pos, len(starttag_text))

    def has_ambiguous_forward_slash(
        self,
        sinfo: OpenTagSourceInfo | TagSourceInfo | None,
        attrs: tuple[TAttribute, ...],
    ) -> bool:
        """
        Detect when an unquoted attribute value consumes a trailing "/" that
        *might* have been meant to attempt to self-close a tag, ie. "/>".

        This can come up with literal values or values with interpolations.

        Such as "<div title=test/>" or "<{Component} title=test/>".

        Or more often "<{Component} title={title}/>" which should be corrected
        with "<{Component} title={title} />".
        """
        source = self.get_source()
        reader = source.get_reader()
        return (
            # has source info
            sinfo is not None
            # has attributes
            and len(attrs) > 0
            # last attribute ends with "/"
            # @NOTE: spread and interpolated attrs never do
            and (
                (
                    isinstance(attrs[-1], TLiteralAttribute)
                    and attrs[-1].value is not None
                    and attrs[-1].value.endswith("/")
                )
                or (
                    isinstance(attrs[-1], TTemplatedAttribute)
                    and attrs[-1].value_ref.strings[-1].endswith("/")
                )
            )
            # original starttag ends with "/>",
            and reader.span_to_template(sinfo.starttag_span).strings[-1].endswith("/>")
            # if parsed AS startend already then its not ambiguous
            and not sinfo.startend
        )

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
            reader = source.get_reader()
            endtag_ref = source.find_placeholders(tag)
            endtag_repr = reader.ref_to_repr(endtag_ref)
            endtag_pos_msg = reader.make_template_pos_msg(endtag_pos)
            if endtag_ref.is_literal or endtag_ref.is_singleton:
                raise ParsingError(
                    f"Unexpected closing tag </{endtag_repr}> with no open tag, {endtag_pos_msg}."
                )
            else:
                raise self.make_invalid_endtag_error(endtag_ref, endtag_pos)
        open_tag = self.stack.pop()
        endtag_i_index = self.validate_end_tag(tag, open_tag)
        final_tag = self.finalize_tag(
            open_tag,
            endtag_i_index=endtag_i_index,
            endtag_pos=endtag_pos,
        )
        self.append_child(final_tag)

    def get_closed_tcomps(
        self, root: OpenTag | None, recurse_component_children: bool = False
    ) -> list[TComponent]:
        """
        Get TComponents that were closed during parsing starting from `root`.

        If `root` is None then use the parser's default `root`.

        TComponents should be returned in the order they were closed in:
        from first closed to last closed.

        @NOTE: That the root is an `OpenTag` but its `children` are actually `TNode`s.
        """
        if root is None:
            root = self.root
        tcomps = []
        nodes = list(root.children)
        while nodes:
            node = nodes.pop()
            if isinstance(node, TComponent):
                tcomps.append(node)
                if recurse_component_children:
                    children = self.tcomponent_children.get(node, [])
                    nodes.extend(children)
            elif isinstance(node, (TElement, TFragment)):
                nodes.extend(node.children)
        return tcomps

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
        self.tcomponent_children = {}

    def run_unclosed_ambiguous_slash_checks(
        self, parent: OpenTag, e: ParsingError
    ) -> None:
        """
        Check for cases where ambiguous slash might create a confusing error.

        @NOTE: This adds exception notes to the exception but does not throw it.
        """
        source = self.get_source()
        reader = source.get_reader()
        if isinstance(
            parent, (OpenTElement, OpenTComponent)
        ) and self.has_ambiguous_forward_slash(parent.sinfo, parent.attrs):
            # CASE: "<{C1} attr={value}/>" -- maybe user meant to self-close?
            # CASE: "<div attr={value}/>" -- mayber user meant to self-close?
            starttag_span = parent.sinfo.starttag_span
            starttag_repr = reader.span_to_repr(starttag_span)
            pos_msg = reader.make_template_pos_msg(parent.source_pos)
            e.add_note(
                f'Did you mean to quote the last attribute or put a space before "/>" for "{starttag_repr}" at {pos_msg}?'
            )
        elif isinstance(parent, OpenTElement):
            # ie. t"<div><div attr={value}/></div>", looks
            # like we missed a closing </div> but really we meant to
            # self-close the middle div.
            children = parent.children[:]
            while children:
                child = children.pop(0)
                if isinstance(child, TElement) and child.tag == parent.tag:
                    sinfo = (
                        self.sinfo_table.get(child.source_pos)
                        if child.source_pos is not None
                        else None
                    )
                    if sinfo and self.has_ambiguous_forward_slash(sinfo, child.attrs):
                        full_starttag_repr = reader.span_to_repr(sinfo.starttag_span)
                        e.add_note(
                            f'Did you mean to quote the last attribute or put a space before "/>" for "{full_starttag_repr}"?'
                        )
                    children.extend(child.children)
        elif isinstance(parent, OpenTComponent):
            # This is a special case where a component accidentally closes
            # another component but we don't check the actual values in
            # the parser so we can't tell until we are generating an error
            # (when we can check the values).
            #
            # CASE: t"<{C2}><{C1} attr=/></{C2}>"
            # Maybe user meant to self-close <{C1} ...>, but closed by </{C2}> leaving <{C2}...> open?
            # CASE: t"<{C3}><{C2}><{C1} attr=/></{C2}></{C3}>"
            for comp in reversed(
                self.get_closed_tcomps(parent, recurse_component_children=True)
            ):
                if (
                    comp.end_i_index is not None
                    and comp.start_i_index != comp.end_i_index
                    and not reader.values_match(comp.start_i_index, comp.end_i_index)
                ):
                    starttag_repr = reader.make_interpolation_repr(comp.start_i_index)
                    endtag_repr = reader.make_interpolation_repr(comp.end_i_index)
                    e.add_note(
                        f"Component start tag, <{starttag_repr} ...>, and end tag, </{endtag_repr}>, have values that do not match."
                    )
                    sinfo = (
                        self.sinfo_table.get(comp.source_pos)
                        if comp.source_pos is not None
                        else None
                    )
                    if sinfo and self.has_ambiguous_forward_slash(sinfo, comp.attrs):
                        full_starttag_repr = reader.span_to_repr(sinfo.starttag_span)
                        e.add_note(
                            f'Did you mean to quote the last attribute or put a space before "/>" for "{full_starttag_repr}"?'
                        )

    def close(self) -> None:
        source = self.get_source()
        if self.waiting_for_data():
            # We apply heuristics here to try to guess why the parser didn't finish.
            if self.rawdata.count('"') % 2 == 1 or self.rawdata.count("'") % 2 == 1:
                raise ParsingError(
                    "Parser expects more data, maybe you left an attribute quote unclosed?"
                )
            else:
                raise ParsingError(
                    "Parser expects more data, is the template valid html?"
                )
        if self.stack:
            parent = self.stack[-1]
            if isinstance(parent, (OpenTElement, OpenTComponent)):
                reader = source.get_reader()
                starttag_repr = reader.span_to_repr(parent.sinfo.starttag_span)
                pos_msg = reader.make_template_pos_msg(parent.source_pos)
                unclosed_msg = f"unclosed tag {starttag_repr} at {pos_msg}"
            else:
                unclosed_msg = "unclosed tags remain"
            e = ParsingError(f"Invalid HTML structure: {unclosed_msg}.")
            self.run_unclosed_ambiguous_slash_checks(parent, e)
            raise e
        if self.source and self.source.has_placeholders():
            raise ParsingError("Some placeholders were never resolved.")
        super().close()

    def waiting_for_data(self):
        return len(self.rawdata) > 0

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
            raise ParsingAssertionError("Source has not been initialized.")
        return self.source

    def track_source(self, template: Template) -> SourceTracker:
        if self.source:
            raise ParsingAssertionError("Did you forget to call reset?")
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
