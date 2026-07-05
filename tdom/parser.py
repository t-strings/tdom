from collections.abc import Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from string.templatelib import Template

from .htmlspec import VOID_ELEMENTS
from .parser_utils import (
    HTMLAttribute,
    ParserPositionTranslator,
    make_parser_pos_translator,
)
from .placeholders import (
    PlaceholderState,
)
from .source import (
    LinePosition,
    PartPosition,
    SourceReader,
)
from .template_utils import TemplateRef, combine_template_refs
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


class ParsingError(Exception):
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

    @TODO: Do we need `ref_attrs` or should we just try to get by with the tattrs?
    """

    starttag_ref: TemplateRef
    " Entire starttag as parsed except placeholders are replaced by references. "
    ref_attrs: tuple[tuple[TemplateRef, TemplateRef | None], ...]
    " Attrs as parsed except placeholders are replaced by references. "
    startend: bool
    " Was parsed as startend tag, ie. <tag />. "
    starttag_pos: PartPosition
    " Template part position of the starttag. "

    def close(self, endtag_pos: PartPosition | None = None) -> TagSourceInfo:
        return TagSourceInfo(
            starttag_ref=self.starttag_ref,
            ref_attrs=self.ref_attrs,
            startend=self.startend,
            starttag_pos=self.starttag_pos,
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
    children_start_s_index: int
    """The strings index where the component's children template starts."""
    offset_into_children_start_s: int
    """The offset INTO the starting string where the component's children template starts."""
    attrs: tuple[TAttribute, ...]
    source_pos: PartPosition
    sinfo: OpenTagSourceInfo
    # @NOTE: The `children` are discarded after parsing and are just used to
    # track template consistency or assist with error reporting.  If the
    # component is processed and returns its children template then that
    # template will be re-parsed (or pulled from the cache).
    children: list[TNode] = field(default_factory=list)


type OpenTag = OpenTElement | OpenTFragment | OpenTComponent


@dataclass
class SourceTracker:
    """Tracks source locations within a Template for error reporting."""

    # TODO: write utilities to generate complete error messages, with the
    # template itself in context and the relevant line/column underlined/etc.

    template: Template

    placeholders: PlaceholderState = field(default_factory=lambda: PlaceholderState())

    index: int = -1

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

    def get_strings_index(self) -> int:
        if self.index % 2 == 0:
            return self.index // 2
        else:
            raise AssertionError(
                f"Index {self.index} is not references an entry in strings."
            )

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


class TemplateParser(HTMLParser):
    root: OpenTFragment
    "Fallback container of parsed nodes if no other topmost container is found."

    stack: list[OpenTag]
    "Stack of tags left open during parsing."

    source: SourceTracker | None
    "Source iterator of template parts, injecting placeholders as needed."

    parser_pos_translator: ParserPositionTranslator | None
    "Translator from parser position to template part position. "

    tcomponent_children: dict[TComponent, list[TNode]]
    "List of children for each finished tcomponent, stored at closing. "

    sinfo_table: dict[PartPosition, TagSourceInfo]
    " Tags with more source info than just a position are tracked in this mapping. "

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
        "Translate the parser position into a part position in the source template."
        return self.get_parser_pos_translator().translate(
            self.get_parser_pos() if parser_pos is None else parser_pos
        )

    # ------------------------------------------
    # Attribute Helpers
    # ------------------------------------------

    def make_tattr(self, attr: HTMLAttribute) -> TAttribute:
        """Build a TAttribute from a raw attribute tuple."""

        name, value = attr
        source = self.get_source()
        name_ref = source.placeholders.remove_placeholders(name)
        value_ref = (
            source.placeholders.remove_placeholders(value)
            if value is not None
            else None
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
            raise AttributeParsingError(
                "Attribute names cannot contain interpolations if the value is also interpolated."
            )
        if not name_ref.is_singleton:
            raise AttributeParsingError(
                "Spread attributes must have exactly one interpolation in the name."
            )
        return TSpreadAttribute(i_index=name_ref.i_indexes[0])

    def make_tattrs(self, attrs: Sequence[HTMLAttribute]) -> tuple[TAttribute, ...]:
        """Build TAttributes from raw attribute tuples."""
        return tuple(self.make_tattr(attr) for attr in attrs)

    def make_ref_attr(
        self, source: SourceTracker, attr: HTMLAttribute
    ) -> tuple[TemplateRef, TemplateRef | None]:
        return (
            source.find_placeholders(attr[0]),
            source.find_placeholders(attr[1]) if attr[1] is not None else None,
        )

    def make_ref_attrs(
        self, attrs: Sequence[HTMLAttribute]
    ) -> tuple[tuple[TemplateRef, TemplateRef | None], ...]:
        source = self.get_source()
        return tuple(self.make_ref_attr(source, attr) for attr in attrs)

    # ------------------------------------------
    # Tag Helpers
    # ------------------------------------------

    def make_open_tag(
        self, tag: str, attrs: Sequence[HTMLAttribute], startend: bool = False
    ) -> OpenTag:
        """Build an OpenTag from a raw tag and attribute tuples."""
        source = self.get_source()
        tag_ref = source.placeholders.remove_placeholders(tag)
        if tag_ref.is_literal:
            source_pos = self.get_source_pos()
            open_tag = OpenTElement(
                tag=tag,
                attrs=self.make_tattrs(attrs),
                sinfo=OpenTagSourceInfo(
                    starttag_ref=self.get_starttag_ref(),
                    ref_attrs=self.make_ref_attrs(attrs),
                    startend=startend,
                    starttag_pos=source_pos,
                ),
                source_pos=source_pos,
            )
            return open_tag

        if not tag_ref.is_singleton:
            raise ParsingError(
                "Component element tags must have exactly one interpolation."
            )

        # HERE BE DRAGONS: the interpolation at i_index should be a
        # component callable. We do not check this in the parser, instead
        # relying on higher layers to validate types and render correctly.
        i_index = tag_ref.i_indexes[0]

        # @NOTE: This must be stored when the tag is handled since it is
        # set based on when the template parts are fed in and otherwise
        # might be out of sync.
        # The starting s_index of the component's children template. Note that
        # this string either contains ">" or " />".  It might not be
        # i_index + 1 because attributes WITHIN the component's tag might
        # contain interpolations causing the i_index (and s_index) to advance
        # arbitrarily.
        children_start_s_index = self.get_source().get_strings_index()

        # @NOTE: This must be called when the tag is handled since it is
        # populated based on the most recently finished start tag. Otherwise
        # the value will be out of sync.
        starttag_ref = self.get_starttag_ref()
        # @NOTE: The last string should terminate the starttag and end with ">"
        # So this length is the offset from the last interpolation to the start
        # of the children's leading string.
        offset_into_children_start_s = len(starttag_ref.strings[-1])

        source_pos = self.get_source_pos()

        open_tag = OpenTComponent(
            start_i_index=i_index,
            children_start_s_index=children_start_s_index,
            offset_into_children_start_s=offset_into_children_start_s,
            attrs=self.make_tattrs(attrs),
            source_pos=source_pos,
            sinfo=OpenTagSourceInfo(
                starttag_ref=starttag_ref,
                ref_attrs=self.make_ref_attrs(attrs),
                startend=startend,
                starttag_pos=source_pos,
            ),
        )
        return open_tag

    def finalize_tag(
        self,
        open_tag: OpenTag,
        endtag_i_index: int | None = None,
        endtag_pos: PartPosition | None = None,
    ) -> TNode:
        """Finalize an OpenTag into a TNode."""
        source = self.get_source()
        match open_tag:
            case OpenTElement(
                tag=tag,
                attrs=attrs,
                children=children,
                source_pos=source_pos,
                sinfo=sinfo,
            ):
                tnode = TElement(
                    tag=tag,
                    attrs=attrs,
                    children=tuple(children),
                    source_pos=source_pos,
                )
                self.sinfo_table[source_pos] = sinfo.close(endtag_pos=endtag_pos)
            case OpenTFragment(children=children, source_pos=source_pos):
                tnode = TFragment(children=tuple(children), source_pos=source_pos)
            case OpenTComponent(
                start_i_index=start_i_index,
                children_start_s_index=children_start_s_index,
                offset_into_children_start_s=offset_into_children_start_s,
                attrs=attrs,
                source_pos=source_pos,
                sinfo=sinfo,
                children=children,
            ):
                children_ref = self.extract_component_children_ref(
                    start_i_index=start_i_index,
                    endtag_i_index=endtag_i_index,
                    children_start_s_index=children_start_s_index,
                    offset_into_children_start_s=offset_into_children_start_s,
                    template=source.template,
                )
                tnode = TComponent(
                    start_i_index=start_i_index,
                    end_i_index=endtag_i_index,
                    children_ref=children_ref,
                    attrs=attrs,
                    source_pos=source_pos,
                )
                self.sinfo_table[source_pos] = sinfo.close(endtag_pos=endtag_pos)
                self.tcomponent_children[tnode] = children
        return tnode

    def extract_component_children_ref(
        self,
        start_i_index: int,
        endtag_i_index: int | None,
        children_start_s_index: int,
        offset_into_children_start_s: int,
        template: Template,
    ) -> TemplateRef:
        """
        Extract the component children template from the entire template.

        We use this template as a "key" into the cache to get the TNode tree.
        """
        if start_i_index != endtag_i_index and endtag_i_index is not None:
            # CASE: <{Comp}>...</{Comp}> or <{Comp}></{Comp}>

            # Use the interpolation index of the callable in the closing tag
            # preceding "string" index is always the same as an interpolation index
            # The "string" should look like this: "...</"
            children_end_s_index = endtag_i_index
            # Offset past the trailing part of the component's start tag to get to
            # where the first "string" of the children's template starts.
            leading = template.strings[children_start_s_index][
                offset_into_children_start_s:
            ]
            if children_start_s_index == children_end_s_index:
                # CASE: Entire children template is a string, leading == trailing.
                leading = leading[: leading.rfind("</")]
                children_ref = TemplateRef(strings=(leading,), i_indexes=())
            else:
                # CASE: Children template contains interpolations so the trailing
                # "string" will not be the same as the leading "string".
                trailing = template.strings[children_end_s_index]
                trailing = trailing[: trailing.rfind("</")]
                children_ref = TemplateRef(
                    strings=(
                        leading,
                        *template.strings[
                            children_start_s_index + 1 : children_end_s_index
                        ],
                        trailing,
                    ),
                    i_indexes=tuple(
                        range(children_start_s_index, children_end_s_index)
                    ),
                )
        else:
            # CASE: <{Comp} /> -- no children template
            children_ref = TemplateRef(strings=("",), i_indexes=())
        return children_ref

    def make_mismatch_error(
        self,
        starttag_sinfo: OpenTagSourceInfo,
        endtag_ref: TemplateRef,
        endtag_pos: PartPosition,
    ) -> ParsingError:
        reader = self.get_source().get_reader()
        starttag_repr = reader.ref_to_repr(starttag_sinfo.starttag_ref)
        starttag_pos_msg = reader.make_template_pos_msg(starttag_sinfo.starttag_pos)
        endtag_repr = reader.ref_to_repr(endtag_ref)
        endtag_pos_msg = reader.make_template_pos_msg(endtag_pos)
        e = ParsingError(
            f"Mismatched closing tag </{endtag_repr}> at {endtag_pos_msg} for {starttag_repr} at {starttag_pos_msg}."
        )
        if self.has_ambiguous_forward_slash(starttag_sinfo):
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
                        open_tag.sinfo, tag_ref, self.get_source_pos()
                    )
                elif not tag_ref.is_singleton and not tag_ref.is_literal:
                    raise self.make_invalid_endtag_error(tag_ref, self.get_source_pos())
                return None
            case OpenTFragment():
                raise ParsingAssertionError("We do not support anonymous fragments.")
            case OpenTComponent():
                if tag_ref.is_literal:
                    raise self.make_mismatch_error(
                        open_tag.sinfo, tag_ref, self.get_source_pos()
                    )
                elif not tag_ref.is_singleton:
                    raise self.make_invalid_endtag_error(tag_ref, self.get_source_pos())
                return tag_ref.i_indexes[0]

    def get_starttag_ref(self) -> TemplateRef:
        """
        Wrap get_starttag_text and just raise if None is returned.

        Do this so we don't guard for `None` everywhere.
        """
        starttag_text = self.get_starttag_text()
        if starttag_text is None:
            raise ParsingAssertionError(
                "Expected the parser to have starttag_text set."
            )
        # @NOTE: We assume the source tracker already manages the placeholders.
        return self.get_source().find_placeholders(starttag_text)

    def has_ambiguous_forward_slash(
        self, sinfo: OpenTagSourceInfo | TagSourceInfo | None
    ) -> bool:
        """
        Detect when an unquoted attribute value consumes a trailing "/" that
        *might* have been meant to attempt to self-close a tag, ie. "/>".

        This can come up with literal values or values with interpolations.

        Such as "<div title=test/>" or "<{Component} title=test/>".

        Or more often "<{Component} title={title}/>" which should be corrected
        with "<{Component} title={title} />".
        """
        if sinfo is not None:
            return (
                # has attributes
                len(sinfo.ref_attrs) > 0
                # last attr not bare attribute
                and sinfo.ref_attrs[-1][1] is not None
                # last char of last string of value of last ref attr is "/"
                and sinfo.ref_attrs[-1][1].strings[-1][-1] == "/"
                # parsed starttag ends with "/>"
                and sinfo.starttag_ref.strings[-1].endswith("/>")
                # if parsed as startend then its not ambiguous
                and not sinfo.startend
            )
        return False

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
                ref=combine_template_refs(prior_text.ref, ref),
                # Keep starting position of the prior text
                source_pos=prior_text.source_pos,
            )
        else:
            self.append_child(TText(ref=ref, source_pos=self.get_source_pos()))

    def handle_comment(self, data: str) -> None:
        source = self.get_source()
        ref = source.remove_placeholders(data)
        comment = TComment(ref, source_pos=self.get_source_pos())
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
        self.parser_pos_translator = None
        self.sinfo_table = {}
        self.tcomponent_children = {}

    def run_unclosed_ambiguous_slash_checks(
        self, parent: OpenTag, e: ParsingError
    ) -> None:
        """
        Check for cases where ambiguous slash might create a confusing error.

        @NOTE: This add exception notes to the exception but does not throw it.
        """
        source = self.get_source()
        reader = source.get_reader()
        if isinstance(
            parent, (OpenTElement, OpenTComponent)
        ) and self.has_ambiguous_forward_slash(parent.sinfo):
            # CASE: "<{C1} attr={value}/>" -- maybe user meant to self-close?
            # CASE: "<div attr={value}/>" -- mayber user meant to self-close?
            starttag_ref = parent.sinfo.starttag_ref
            starttag_repr = reader.ref_to_repr(starttag_ref)
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
                    if sinfo and self.has_ambiguous_forward_slash(sinfo):
                        full_starttag_repr = reader.ref_to_repr(sinfo.starttag_ref)
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
                    if sinfo and self.has_ambiguous_forward_slash(sinfo):
                        full_starttag_repr = reader.ref_to_repr(sinfo.starttag_ref)
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
            e = ParsingError("Invalid HTML structure: unclosed tags remain.")
            self.run_unclosed_ambiguous_slash_checks(self.stack[-1], e)
            raise e
        if not source.placeholders.is_empty:
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
            # This would be a bug.
            raise AssertionError("Source has not been initialized.")
        return self.source

    def get_parser_pos_translator(self) -> ParserPositionTranslator:
        if self.parser_pos_translator is None:
            raise AssertionError("Parser position translator has not been initialized.")
        return self.parser_pos_translator

    def feed_template(self, template: Template) -> None:
        """Feed a Template's content to the parser."""
        assert self.source is None, "Did you forget to call reset?"
        self.source = SourceTracker(template)
        self.parser_pos_translator = make_parser_pos_translator(
            template, self.source.placeholders.config
        )
        for content in self.source:
            self.feed(content)

    @staticmethod
    def parse(t: Template) -> TNode:
        """
        Parse a Template containing valid HTML and substitutions and return
        a cacheable TNode tree representing its structure.

        A placeholder config must be passed to keep parser positions consistent
        between calls.
        """
        return TemplateParser.parse_to_ttree(t).root

    @staticmethod
    def parse_to_ttree(t: Template) -> TTree:
        parser = TemplateParser()
        parser.feed_template(t)
        parser.close()
        return parser.get_ttree()
