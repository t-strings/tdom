import typing as t
from dataclasses import dataclass, field

from .template_utils import TemplateRef


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

    @classmethod
    def empty(cls) -> t.Self:
        return cls(TemplateRef.empty())

    @classmethod
    def literal(cls, text: str) -> t.Self:
        return cls(TemplateRef.literal(text))


@dataclass(slots=True, frozen=True)
class TComment(TNode):
    ref: TemplateRef

    @classmethod
    def literal(cls, text: str) -> t.Self:
        return cls(TemplateRef.literal(text))


@dataclass(slots=True, frozen=True)
class TDocumentType(TNode):
    text: str


@dataclass(slots=True, frozen=True)
class TFragment(TNode):
    children: tuple[TNode, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class TElement(TNode):
    tag: str
    attrs: tuple[TAttribute, ...] = field(default_factory=tuple)
    children: tuple[TNode, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class TComponent(TNode):
    start_i_index: int
    """The interpolation index for the component's starting tag name."""

    end_i_index: int | None = None
    """The interpolation index for the component's ending tag name, if any."""

    # TODO: hold on to _s_indexes too, when we start to need them.

    attrs: tuple[TAttribute, ...] = field(default_factory=tuple)
    children: tuple[TNode, ...] = field(default_factory=tuple)


type TParentNode = TElement | TComponent | TFragment
