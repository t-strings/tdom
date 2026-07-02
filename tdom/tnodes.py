import typing as t
from dataclasses import dataclass, field

from .template_utils import PartPosition, TemplateRef


@dataclass(slots=True, frozen=True)
class TLiteralAttribute:
    name: str
    value: str | None


@dataclass(slots=True, frozen=True)
class TInterpolatedAttribute:
    name: str
    value_i_index: int


@dataclass(slots=True, frozen=True)
class TTemplatedAttribute:
    name: str
    value_ref: TemplateRef


@dataclass(slots=True, frozen=True)
class TSpreadAttribute:
    i_index: int


type TAttribute = (
    TLiteralAttribute | TTemplatedAttribute | TInterpolatedAttribute | TSpreadAttribute
)


@dataclass(slots=True, frozen=True)
class TNode:
    def __html__(self) -> str:
        raise NotImplementedError("Cannot render TNode to HTML directly.")

    def __str__(self) -> str:
        raise NotImplementedError("Cannot render TNode to string directly.")


@dataclass(slots=True, frozen=True)
class TText(TNode):
    ref: TemplateRef

    source_pos: PartPosition | None = field(default=None, compare=False)

    @classmethod
    def empty(cls) -> t.Self:
        return cls(TemplateRef.empty())

    @classmethod
    def literal(cls, text: str) -> t.Self:
        return cls(TemplateRef.literal(text))


@dataclass(slots=True, frozen=True)
class TComment(TNode):
    ref: TemplateRef

    source_pos: PartPosition | None = field(default=None, compare=False)

    @classmethod
    def literal(cls, text: str) -> t.Self:
        return cls(TemplateRef.literal(text))


@dataclass(slots=True, frozen=True)
class TDocumentType(TNode):
    text: str

    source_pos: PartPosition | None = field(default=None, compare=False)


@dataclass(slots=True, frozen=True)
class TFragment(TNode):
    children: tuple[TNode, ...] = field(default_factory=tuple)

    source_pos: PartPosition | None = field(default=None, compare=False)


@dataclass(slots=True, frozen=True)
class TElement(TNode):
    tag: str
    attrs: tuple[TAttribute, ...] = field(default_factory=tuple)
    children: tuple[TNode, ...] = field(default_factory=tuple)

    source_pos: PartPosition | None = field(default=None, compare=False)


@dataclass(slots=True, frozen=True)
class TComponent(TNode):
    start_i_index: int
    """The interpolation index for the component's starting tag name."""

    end_i_index: int | None = None
    """The interpolation index for the component's ending tag name, if any."""

    children_ref: TemplateRef = field(
        default_factory=lambda: TemplateRef(strings=("",), i_indexes=())
    )
    """The template ref that describes the component's children template."""

    attrs: tuple[TAttribute, ...] = field(default_factory=tuple)

    source_pos: PartPosition | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class TagSourceInfo:
    """
    Retained tag information from the parsed source meant for error reporting.

    @NOTE: This must be cacheable so it should not directly reference a
    template instance.
    """

    starttag_ref: TemplateRef
    " Entire starttag as parsed except placeholders are replaced by references. "
    ref_attrs: tuple[tuple[TemplateRef, TemplateRef | None], ...]
    " Attrs as parsed except placeholders are replaced by references. "
    startend: bool
    " Was parsed as startend tag, ie. <tag />. "
    starttag_pos: PartPosition
    " Template part position of the starttag, ie. <tag> or <tag />. "
    endtag_pos: PartPosition | None = None
    " Template part position of the endtag, ie. </tag>. "


@dataclass
class TTree:
    root: TNode

    sinfos: tuple[TagSourceInfo, ...] = ()

    def unpack_sinfo_table(self) -> dict[PartPosition, TagSourceInfo]:
        return {sinfo.starttag_pos: sinfo for sinfo in self.sinfos}


type TTag = TElement | TComponent | TFragment
