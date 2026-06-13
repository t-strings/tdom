from collections.abc import Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from string.templatelib import Interpolation, Template

from .htmlspec import VOID_ELEMENTS, NamespaceType
from .placeholders import PlaceholderConfig, PlaceholderState
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
)

type HTMLAttribute = tuple[str, str | None]
type HTMLAttributesDict = dict[str, str | None]


@dataclass
class ParseInfo:
    starttag_text: str
    " Entire starttag as parsed, includes placeholders, used for debugging. "
    raw_attrs: Sequence[HTMLAttribute]
    " Attrs as parsed, includes placeholders, used for debugging. "
    startend: bool
    " Was parsed as startend tag, ie. <tag />, used for debugging. "


@dataclass
class OpenTElement:
    parse_info: ParseInfo
    tag: str
    attrs: tuple[TAttribute, ...]
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTFragment:
    children: list[TNode] = field(default_factory=list)


@dataclass
class OpenTComponent:
    parse_info: ParseInfo
    start_i_index: int
    children_start_s_index: int
    """The strings index where the component's children template starts."""
    offset_into_children_start_s: int
    """The offset INTO the starting string where the component's children template starts."""
    attrs: tuple[TAttribute, ...]
    # @NOTE: The `children` are discarded after parsing and are just used to
    # track template consistency.  If the component is processed and
    # returns its children template then that template will be
    # re-parsed (or pulled from the cache).
    children: list[TNode] = field(default_factory=list)


type OpenTag = OpenTElement | OpenTFragment | OpenTComponent


@dataclass
class SourceTracker:
    """Tracks source locations within a Template for error reporting."""

    # TODO: write utilities to generate complete error messages, with the
    # template itself in context and the relevant line/column underlined/etc.

    template: Template
    # if i_index >= s_index, feeding an interpolation;
    # otherwise, when i_index < s_index, feeding a string.
    i_index: int = -1  # The current interpolation index.
    s_index: int = -1  # The current string index.

    @property
    def interpolations(self) -> tuple[Interpolation, ...]:
        return self.template.interpolations

    def _check_indices(self, index1: int, index2: int):
        last_index = len(self.interpolations) - 1
        if max(index1, index2) > last_index or min(index1, index2) < 0:
            raise ValueError(
                f"Interpolation indices exceed bounds: {index1} {index2}: [0...{last_index}]"
            )

    def expressions_match(self, i_index1: int, i_index2: int) -> bool:
        self._check_indices(i_index1, i_index2)
        return (
            self.interpolations[i_index1].expression
            == self.interpolations[i_index2].expression
        )

    def values_match(self, i_index1: int, i_index2: int) -> bool:
        self._check_indices(i_index1, i_index2)
        return (
            self.interpolations[i_index1].value == self.interpolations[i_index2].value
        )

    def advance_interpolation(self) -> int:
        """Call before processing an interpolation to move to the next one."""
        self.i_index += 1
        return self.i_index

    def advance_string(self) -> int:
        self.s_index += 1
        return self.s_index

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


@dataclass(frozen=True)
class ParseContext:
    """
    This is the context that was used to parse a given template.
    """

    # @TODO: slots might have issue with weakref, check if caching that
    # is an issue.

    ns: NamespaceType = "html"

    def copy(self, ns: NamespaceType | None = None) -> ParseContext:
        return ParseContext(ns=ns if ns is not None else self.ns)


@dataclass(frozen=True)
class InternalParseContext:
    """
    This is the context that was used to parse a given template.
    """

    ns: NamespaceType = "html"
    in_component: bool = False

    def copy(
        self, ns: NamespaceType | None = None, in_component: bool | None = None
    ) -> InternalParseContext:
        return InternalParseContext(
            ns=ns if ns is not None else self.ns,
            in_component=in_component
            if in_component is not None
            else self.in_component,
        )


class TemplateParser(HTMLParser):
    root: OpenTFragment
    stack: list[tuple[OpenTag, InternalParseContext]]
    placeholders: PlaceholderState
    source: SourceTracker | None
    root_ctx: InternalParseContext
    " Assume that template parsing *starts* in this context. "

    def __init__(
        self, *, root_ctx: InternalParseContext, convert_charrefs: bool = True
    ):
        self.root_ctx = root_ctx
        # This calls HTMLParser.reset() which we override to set up our state.
        super().__init__(convert_charrefs=convert_charrefs)

    # ------------------------------------------
    # Parse state helpers
    # ------------------------------------------

    def get_parent(self) -> OpenTag:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1][0] if self.stack else self.root

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
        tag_ref = self.placeholders.remove_placeholders(tag)

        if tag_ref.is_literal:
            return OpenTElement(
                parse_info=ParseInfo(
                    starttag_text=self.get_starttag_text(),
                    raw_attrs=attrs,
                    startend=startend,
                ),
                tag=tag,
                attrs=self.make_tattrs(attrs),
            )

        if not tag_ref.is_singleton:
            raise ValueError(
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
            config=self.placeholders.config,
            starttag_text=starttag_text,
        )

        return OpenTComponent(
            parse_info=ParseInfo(
                starttag_text=starttag_text, raw_attrs=attrs, startend=startend
            ),
            start_i_index=i_index,
            children_start_s_index=children_start_s_index,
            offset_into_children_start_s=offset_into_children_start_s,
            attrs=tattrs,
        )

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
            raise AssertionError(
                "There are extra placeholders still in the starttag_text."
            )
        # Now the last string should terminate the starttag and end with ">"
        # So this length is the offset from the last interpolation to the start
        # of the children's leading string.
        return len(tag_ref.strings[-1])

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
                children_start_s_index=children_start_s_index,
                offset_into_children_start_s=offset_into_children_start_s,
                attrs=attrs,
            ):
                children_ref = self.extract_component_children_ref(
                    start_i_index=start_i_index,
                    endtag_i_index=endtag_i_index,
                    children_start_s_index=children_start_s_index,
                    offset_into_children_start_s=offset_into_children_start_s,
                    template=self.get_source().template,
                )
                return TComponent(
                    start_i_index=start_i_index,
                    end_i_index=endtag_i_index,
                    children_ref=children_ref,
                    attrs=attrs,
                )

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
                    starttag = source.format_starttag(start_i_index)
                    e = ValueError(
                        f"Mismatched closing tag </{tag}> for component with tag {{{starttag}}}."
                    )
                    if self.has_ambiguous_forward_slash(open_tag):
                        e.add_note(
                            f'Did you mean to quote the last attribute or put a space before "/>" for "<{{{starttag}}} .../>"?'
                        )
                    raise e
                if not tag_ref.is_singleton:
                    raise ValueError(
                        "Component end tags must have exactly one interpolation."
                    )
                if not source.expressions_match(
                    open_tag.start_i_index, tag_ref.i_indexes[0]
                ) and not source.values_match(
                    open_tag.start_i_index, tag_ref.i_indexes[0]
                ):
                    e = TypeError(
                        "Component start and end tags must contain the same callable."
                    )
                    if self.has_ambiguous_forward_slash(open_tag):
                        starttag = source.format_starttag(start_i_index)
                        e.add_note(
                            f'Did you mean to quote the last attribute or put a space before "/>" for "<{{{starttag}}} .../>"?'
                        )
                    raise e
                return tag_ref.i_indexes[0]

    def get_starttag_text(self, msg: str = "Expecting starttag text to be set.") -> str:
        """
        Wrap get_starttag_text and just raise if None is returned.

        Do this so we don't guard for `None` everywhere.
        """
        starttag_text = super().get_starttag_text()
        if starttag_text is None:
            raise AssertionError(msg)
        return starttag_text

    def get_last_ctx(self) -> InternalParseContext:
        if self.stack:
            return self.stack[-1][1]
        else:
            return self.root_ctx

    def is_literal_tag(self, tag: str):
        return self.placeholders.copy().remove_placeholders(tag).is_literal

    def validate_self_close_attempt(self, last_ctx: InternalParseContext, tag: str):
        if (
            not last_ctx.in_component
            and last_ctx.ns == "html"
            # @NOTE: Only void tags can be losed when NS is explictly html.
            and tag not in VOID_ELEMENTS
        ):
            e = ValueError(
                "Self-closing tags are only supported for components and void tags in html."
            )
            e.add_note(f"Cannot self-close {tag}.")
            raise e

    def has_ambiguous_forward_slash(self, open_tag: OpenTag) -> bool:
        """
        Detect when an unquoted attribute value consumes a trailing "/" that
        *might* have been meant to attempt to self-close a tag, ie. "/>".

        This can come up with literal values or values with interpolations.

        Such as "<div title=test/>" or "<{Component} title=test/>".

        Or more often "<{Component} title={title}/>" which should be corrected
        with "<{Component} title={title} />".
        """
        if isinstance(open_tag, (OpenTElement, OpenTComponent)):
            info = open_tag.parse_info
            return (
                # has attributes
                len(info.raw_attrs) > 0
                # last attr not bare attribute
                and info.raw_attrs[-1][1] is not None
                # last char of last attr is "/"
                and info.raw_attrs[-1][1][-1] == "/"
                # parsed starttag ends with "/>"
                and info.starttag_text.endswith("/>")
                # if parsed as startend then its not ambiguous
                and not info.startend
            )
        return False

    # ------------------------------------------
    # HTMLParser tag callbacks
    # ------------------------------------------

    def handle_starttag(self, tag: str, attrs: Sequence[HTMLAttribute]) -> None:
        open_tag = self.make_open_tag(tag, attrs)
        last_ctx = self.get_last_ctx()
        if (
            isinstance(open_tag, OpenTElement)
            and open_tag.tag in VOID_ELEMENTS
            and (
                last_ctx.ns == "html"
                # @TODO: Maybe backtracking when it looks like we needed
                # to close it would be better? We just need the component's
                # children to parse out and get out of the way because that
                # isn't the template we are trying to parse and cache.
                or last_ctx.in_component
            )
        ):
            final_tag = self.finalize_tag(open_tag)
            self.append_child(final_tag)
        else:
            last_ctx = self.get_last_ctx()
            if isinstance(open_tag, OpenTElement):
                if open_tag.tag == "svg":
                    next_ctx = last_ctx.copy(ns="svg")
                elif open_tag.tag == "math":
                    next_ctx = last_ctx.copy(ns="math")
                elif open_tag.tag == "foreignobject" and last_ctx.ns in ("svg", "math"):
                    next_ctx = last_ctx.copy(ns="html")
                else:
                    next_ctx = last_ctx
            elif isinstance(open_tag, OpenTComponent):
                next_ctx = last_ctx.copy(in_component=True)
            else:
                next_ctx = last_ctx
            self.stack.append((open_tag, next_ctx))

    def handle_startendtag(self, tag: str, attrs: Sequence[HTMLAttribute]) -> None:
        """Dispatch a self-closing tag, `<tag />` to specialized handlers."""
        if self.is_literal_tag(tag):
            last_ctx = self.get_last_ctx()
            self.validate_self_close_attempt(last_ctx, tag)

        open_tag = self.make_open_tag(tag, attrs, startend=True)
        final_tag = self.finalize_tag(open_tag)
        self.append_child(final_tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            raise ValueError(f"Unexpected closing tag </{tag}> with no open tag.")

        open_tag, _ = self.stack.pop()
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
        if self.waiting_for_data():
            # We apply heuristics here to try to guess why the parser didn't finish.
            if self.rawdata.count('"') % 2 == 1 or self.rawdata.count("'") % 2 == 1:
                raise ValueError(
                    "Parser expects more data, maybe you left an attribute quote unclosed?"
                )
            else:
                raise ValueError(
                    "Parser expects more data, is the template valid html?"
                )
        if self.stack:
            e = ValueError("Invalid HTML structure: unclosed tags remain.")
            # Check for tags that might have meant to self-close but whose
            # unquoted last attribute value consumed a "/", ie. <div id=app/>.
            parent, _ = self.stack[-1]
            # @TODO: We need to determine which tags this might apply to, this only applies to components.
            if isinstance(parent, OpenTComponent) and self.has_ambiguous_forward_slash(
                parent
            ):
                starttag = (
                    f"{{{self.get_source().format_starttag(parent.start_i_index)}}}"
                )
                e.add_note(
                    f'Did you mean to quote the last attribute or put a space before "/>" for "<{starttag} .../>"?'
                )
            raise e
        if not self.placeholders.is_empty:
            raise ValueError("Some placeholders were never resolved.")
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

    # ------------------------------------------
    # Feeding and parsing
    # ------------------------------------------

    def get_source(self) -> SourceTracker:
        if self.source is None:
            raise AssertionError("Source has not been initialized.")
        return self.source

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
            self.source.advance_string()
            self.feed_str(template.strings[i_index])
            self.source.advance_interpolation()
            self.feed_interpolation(i_index)
        self.source.advance_string()
        self.feed_str(template.strings[-1])

    @staticmethod
    def parse(t: Template, assume_ctx: ParseContext | None = None) -> TNode:
        """
        Parse a Template containing valid HTML and substitutions and return
        a TNode tree representing its structure. This cachable structure can later
        be resolved against actual interpolation values to produce a Node tree.
        """
        if assume_ctx is None:
            assume_ctx = ParseContext()
        parser = TemplateParser(root_ctx=InternalParseContext(ns=assume_ctx.ns))
        parser.feed_template(t)
        parser.close()
        return parser.get_tnode()
