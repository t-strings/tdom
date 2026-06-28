from collections.abc import Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from string.templatelib import Interpolation, Template

from .htmlspec import VOID_ELEMENTS
from .parser_utils import HTMLAttribute
from .placeholders import (
    PlaceholderConfig,
    PlaceholderState,
    make_placeholder_config,
)
from .source import (
    FrozenPosition,
    SourceReader,
    TagSourceInfo,
)
from .template_utils import TemplateRef, combine_template_refs
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
    Retained tag information from the parsed source.

    @NOTE: These properties DEPEND on the placeholder configuration because
    they can contain embedded placeholders.
    """

    starttag_text: str
    " Entire starttag as parsed, includes placeholders, . "
    raw_attrs: tuple[HTMLAttribute, ...]
    " Attrs as parsed, includes placeholders. "
    startend: bool
    " Was parsed as startend tag, ie. <tag />. "
    starttag_pos: FrozenPosition
    " Position of the parser when the element starttag was parsed. "

    def close(self, endtag_pos: FrozenPosition | None = None) -> TagSourceInfo:
        return TagSourceInfo(
            starttag_text=self.starttag_text,
            raw_attrs=self.raw_attrs,
            startend=self.startend,
            starttag_pos=self.starttag_pos,
            endtag_pos=endtag_pos,
        )


@dataclass
class OpenTElement:
    tag: str
    attrs: tuple[TAttribute, ...]
    parser_pos: FrozenPosition
    sinfo: OpenTagSourceInfo
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTFragment:
    parser_pos: FrozenPosition | None = None
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTComponent:
    start_i_index: int
    children_start_s_index: int
    """The strings index where the component's children template starts."""
    offset_into_children_start_s: int
    """The offset INTO the starting string where the component's children template starts."""
    attrs: tuple[TAttribute, ...]
    parser_pos: FrozenPosition
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

    placeholders: PlaceholderState

    # if i_index >= s_index, feeding an interpolation;
    # otherwise, when i_index < s_index, feeding a string.
    i_index: int = -1  # The current interpolation index.
    s_index: int = -1  # The current string index.

    def __iter__(self):
        return self

    def __next__(self):
        if self.i_index < self.s_index:
            # Advance into the next interpolation UNLESS the last string
            # we returned was at the end of the template.
            if self.s_index == len(self.template.strings) - 1:
                raise StopIteration
            self.i_index += 1
            return self.placeholders.add_placeholder(self.i_index)
        elif self.i_index == self.s_index:
            # Advance into the next string
            self.s_index += 1
            return self.template.strings[self.s_index]
        else:
            raise AssertionError("{self.i_index=} should not exceed {self.s_index=}")

    @property
    def interpolations(self) -> tuple[Interpolation, ...]:
        return self.template.interpolations

    def values_match(self, i_index1: int, i_index2: int) -> bool:
        return (
            self.interpolations[i_index1].value == self.interpolations[i_index2].value
        )

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

    def format_endtag(self, i_index: int) -> str:
        return self.get_expression(i_index, fallback_prefix="component-endtag")

    def get_reader(self) -> SourceReader:
        return SourceReader(
            template=self.template, placeholder_config=self.placeholders.config
        )


class TemplateParser(HTMLParser):
    root: OpenTFragment
    stack: list[OpenTag]
    source: SourceTracker | None
    " Map from completed tnodes back to their opentag for error reporting. "
    tcomponent_children: dict[TComponent, list[TNode]]
    "List of children for each finished tcomponent, stored at closing. "
    sinfo_table: dict[FrozenPosition, TagSourceInfo]
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

    def get_parser_pos(self) -> FrozenPosition:
        """
        Get the current position of the parser.

        @NOTE: This position is relative to text embedded with placeholders but
        can be translated back to the position within the original template.
        Since it *IS* relative to placeholders, ie. "SLOTS", this position is
        unique across a "family" of templates with the same structure.
        """
        line, offset = self.getpos()
        return FrozenPosition(line=line, offset=offset)

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
            parser_pos = self.get_parser_pos()
            open_tag = OpenTElement(
                tag=tag,
                attrs=self.make_tattrs(attrs),
                sinfo=OpenTagSourceInfo(
                    starttag_text=self.get_starttag_text(),
                    raw_attrs=tuple(attrs),
                    startend=startend,
                    starttag_pos=parser_pos,
                ),
                parser_pos=parser_pos,
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
        children_start_s_index = self.get_source().s_index

        # @NOTE: This must be called when the tag is handled since it is
        # populated based on the most recently finished start tag. Otherwise
        # the value will be out of sync.
        starttag_text = self.get_starttag_text(
            f"Expected startag_text to be set when parsing component at {i_index}."
        )

        tattrs = self.make_tattrs(attrs)

        offset_into_children_start_s = self.compute_offset_into_children_start_s(
            start_i_index=i_index,
            tattrs=tattrs,
            config=source.placeholders.config,
            starttag_text=starttag_text,
        )

        parser_pos = self.get_parser_pos()
        open_tag = OpenTComponent(
            start_i_index=i_index,
            children_start_s_index=children_start_s_index,
            offset_into_children_start_s=offset_into_children_start_s,
            attrs=tattrs,
            parser_pos=parser_pos,
            sinfo=OpenTagSourceInfo(
                starttag_text=starttag_text,
                raw_attrs=tuple(attrs),
                startend=startend,
                starttag_pos=parser_pos,
            ),
        )
        return open_tag

    def compute_offset_into_children_start_s(
        self,
        start_i_index: int,
        tattrs: tuple[TAttribute, ...],
        config: PlaceholderConfig,
        starttag_text: str,
    ) -> int:
        """
        Compute offset into "string" containing the start of children template.

        @NOTE: This is to actually OFFLOAD work to the parser itself.  If we try
        to "rebuild" the tag from the parse result we are bound to fail in some
        way(s). We essentially re-run the placeholder process but with content
        we KNOWN ends at the end of the starttag, ie. ">", because the parser
        told us that is where it ends (rather than trying to scan for ">"
        because ">" might be in literal tags).

        Examples:

        <{Comp}></{Comp}> -- len(">")
        <{Comp}>children</{Comp}> -- len(">")
        <{Comp} title="1>0">children</{Comp}> -- len(' title="1>0">')
        <{Comp} title="{'1>0'}">children</{Comp}> -- len('">')
        """
        # Rebuild known interpolations in the starttag.
        known: set[int] = {start_i_index}  # The component callable itself.
        for attr in tattrs:
            if isinstance(attr, TInterpolatedAttribute):
                known.add(attr.value_i_index)
            elif isinstance(attr, TSpreadAttribute):
                known.add(attr.i_index)
            elif isinstance(attr, TTemplatedAttribute):
                known.update(attr.value_ref.i_indexes)
        # Now re-remove those placeholders using the same config we used to
        # make them.
        temp_placeholders = PlaceholderState(known=known, config=config)
        tag_ref = temp_placeholders.remove_placeholders(starttag_text)
        if not temp_placeholders.is_empty:
            raise ParsingAssertionError(
                "There are extra placeholders still in the starttag_text."
            )
        # Now the last string should terminate the starttag and end with ">"
        # So this length is the offset from the last interpolation to the start
        # of the children's leading string.
        return len(tag_ref.strings[-1])

    def finalize_tag(
        self,
        open_tag: OpenTag,
        endtag_i_index: int | None = None,
        endtag_pos: FrozenPosition | None = None,
    ) -> TNode:
        """Finalize an OpenTag into a TNode."""
        source = self.get_source()
        match open_tag:
            case OpenTElement(
                tag=tag,
                attrs=attrs,
                children=children,
                parser_pos=parser_pos,
                sinfo=sinfo,
            ):
                tnode = TElement(
                    tag=tag,
                    attrs=attrs,
                    children=tuple(children),
                    parser_pos=parser_pos,
                )
                self.sinfo_table[parser_pos] = sinfo.close(endtag_pos=endtag_pos)
            case OpenTFragment(children=children, parser_pos=parser_pos):
                tnode = TFragment(children=tuple(children), parser_pos=parser_pos)
            case OpenTComponent(
                start_i_index=start_i_index,
                children_start_s_index=children_start_s_index,
                offset_into_children_start_s=offset_into_children_start_s,
                attrs=attrs,
                parser_pos=parser_pos,
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
                    parser_pos=parser_pos,
                )
                self.sinfo_table[parser_pos] = sinfo.close(endtag_pos=endtag_pos)
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

    def validate_end_tag(self, tag: str, open_tag: OpenTag) -> int | None:
        """Validate that closing tag matches open tag. Return component end index if applicable."""
        source = self.get_source()
        tag_ref = source.placeholders.remove_placeholders(tag)

        match open_tag:
            case OpenTElement():
                if not tag_ref.is_literal:
                    raise ParsingError(
                        f"Component closing tag found for element <{open_tag.tag}>."
                    )
                if tag != open_tag.tag:
                    raise ParsingError(
                        f"Mismatched closing tag </{tag}> for element <{open_tag.tag}>."
                    )
                return None

            case OpenTFragment():
                raise ParsingAssertionError("We do not support anonymous fragments.")

            case OpenTComponent(start_i_index=start_i_index):
                if tag_ref.is_literal:
                    starttag = source.format_starttag(start_i_index)
                    e = ParsingError(
                        f"Mismatched closing tag </{tag}> for component with tag {{{starttag}}}."
                    )
                    if self.has_ambiguous_forward_slash(open_tag.sinfo):
                        e.add_note(
                            f'Did you mean to quote the last attribute or put a space before "/>" for "<{{{starttag}}} .../>"?'
                        )
                    raise e
                if not tag_ref.is_singleton:
                    raise ParsingError(
                        "Component end tags must have exactly one interpolation."
                    )
                return tag_ref.i_indexes[0]

    def get_starttag_text(self, msg: str = "Expecting starttag text to be set.") -> str:
        """
        Wrap get_starttag_text and just raise if None is returned.

        Do this so we don't guard for `None` everywhere.
        """
        starttag_text = super().get_starttag_text()
        if starttag_text is None:
            raise ParsingAssertionError(msg)
        return starttag_text

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
                len(sinfo.raw_attrs) > 0
                # last attr not bare attribute
                and sinfo.raw_attrs[-1][1] is not None
                # last char of last attr is "/"
                and sinfo.raw_attrs[-1][1][-1] == "/"
                # parsed starttag ends with "/>"
                and sinfo.starttag_text.endswith("/>")
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
        if not self.stack:
            source = self.get_source()
            tag_ref = source.placeholders.copy().remove_placeholders(tag)
            if tag_ref.is_literal:
                reader = source.get_reader()
                pos_msg = reader.make_template_pos_msg(self.get_parser_pos())
                raise ParsingError(f"Unexpected closing tag </{tag}> with no open tag, {pos_msg}.")
            if not tag_ref.is_singleton:
                # @TODO: Also it doesn't match anything
                raise ParsingError(
                    "Component end tags must have exactly one interpolation."
                )
            # Component tag endtag but no component tag is open...
            unmatched_endtag = self.get_source().format_endtag(tag_ref.i_indexes[0])
            raise ParsingError(
                f"Unexpected closing component tag </{{{unmatched_endtag}}}> with no open tag."
            )
        open_tag = self.stack.pop()
        endtag_i_index = self.validate_end_tag(tag, open_tag)
        final_tag = self.finalize_tag(
            open_tag, endtag_i_index=endtag_i_index, endtag_pos=self.get_parser_pos()
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
        ref = source.placeholders.remove_placeholders(data)
        parent = self.get_parent()
        if parent.children and isinstance(parent.children[-1], TText):
            prior_text = parent.children[-1]
            parent.children[-1] = TText(
                ref=combine_template_refs(prior_text.ref, ref),
                # Keep starting position of the prior text
                parser_pos=prior_text.parser_pos,
            )
        else:
            self.append_child(TText(ref=ref, parser_pos=self.get_parser_pos()))

    def handle_comment(self, data: str) -> None:
        source = self.get_source()
        ref = source.placeholders.remove_placeholders(data)
        comment = TComment(ref, parser_pos=self.get_parser_pos())
        self.append_child(comment)

    def handle_decl(self, decl: str) -> None:
        source = self.get_source()
        ref = source.placeholders.remove_placeholders(decl)
        if not ref.is_literal:
            raise ParsingError("Interpolations are not allowed in declarations.")
        elif decl.upper().startswith("DOCTYPE "):
            doctype_content = decl[7:].strip()
            doctype = TDocumentType(doctype_content, parser_pos=self.get_parser_pos())
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
            # @TODO: We need to determine which tags this might apply to,
            # this only applies to components.
            parent = self.stack[-1]
            if isinstance(parent, OpenTComponent) and self.has_ambiguous_forward_slash(
                parent.sinfo
            ):
                # CASE: "<{C1} attr={value}/>" -- meant to self-close
                # Maybe user meant to self-close?
                starttag = source.format_starttag(parent.start_i_index)
                e.add_note(
                    f'Did you mean to quote the last attribute or put a space before "/>" for "<{{{starttag}}} .../>"?'
                )
            else:
                # CASE: t"<{C2}><{C1} attr=/></{C2}>"
                # Maybe user meant to self-close <{C1} ...>, but closed by </{C2}> leaving <{C2}...> open?
                # CASE: t"<{C3}><{C2}><{C1} attr=/></{C2}></{C3}>"
                for comp in reversed(
                    self.get_closed_tcomps(parent, recurse_component_children=True)
                ):
                    if (
                        comp.end_i_index is not None
                        and comp.start_i_index != comp.end_i_index
                        and not source.values_match(
                            comp.start_i_index, comp.end_i_index
                        )
                    ):
                        sinfo = (
                            self.sinfo_table.get(comp.parser_pos)
                            if comp.parser_pos is not None
                            else None
                        )
                        starttag = source.format_starttag(comp.start_i_index)
                        endtag = source.format_endtag(comp.end_i_index)
                        e.add_note(
                            f"Component start tag, <{{{starttag}}}>, and end tag, </{{{endtag}}}>, have values that do not match."
                        )
                        if self.has_ambiguous_forward_slash(sinfo):
                            e.add_note(
                                f'Did you mean to quote the last attribute or put a space before "/>" for "<{{{starttag}}} .../>"?'
                            )
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
            placeholder_config=self.get_source().placeholders.config,
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

    def feed_template(
        self, template: Template, placeholder_config: PlaceholderConfig
    ) -> None:
        """Feed a Template's content to the parser."""
        assert self.source is None, "Did you forget to call reset?"
        self.source = SourceTracker(
            template, placeholders=PlaceholderState(config=placeholder_config)
        )
        for content in self.source:
            self.feed(content)

    @staticmethod
    def parse(
        t: Template, placeholder_config: PlaceholderConfig | None = None
    ) -> TNode:
        """
        Parse a Template containing valid HTML and substitutions and return
        a cacheable TNode tree representing its structure.

        A placeholder config must be passed to keep parser positions consistent
        between calls.
        """
        return TemplateParser.parse_to_ttree(t, placeholder_config).root

    @staticmethod
    def parse_to_ttree(
        t: Template, placeholder_config: PlaceholderConfig | None = None
    ) -> TTree:
        if placeholder_config is None:
            placeholder_config = make_placeholder_config()
        parser = TemplateParser()
        parser.feed_template(t, placeholder_config=placeholder_config)
        parser.close()
        return parser.get_ttree()
