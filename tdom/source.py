from dataclasses import dataclass

from .parser_utils import HTMLAttribute


@dataclass(slots=True, frozen=True)
class FrozenPosition:
    "A immutable position in a block of source code."

    line: int = 1
    " Line of code, starts at 1. "
    offset: int = 0
    " Offset from the start of the line, starts at 0. "


@dataclass(slots=True)
class Position:
    "A position in a block of source code."

    line: int = 1
    " Line of code, starts at 1. "
    offset: int = 0
    " Offset from the start of the line, starts at 0. "

    def freeze(self) -> FrozenPosition:
        return FrozenPosition(line=self.line, offset=self.offset)


@dataclass(frozen=True, slots=True)
class TagSourceInfo:
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
    endtag_pos: FrozenPosition | None = None
    " Position of the parser when the element endtag was parsed. "
