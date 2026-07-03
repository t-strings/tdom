from collections.abc import Callable
from string.templatelib import Template

import pytest

from .parser_utils import ParserPositionTranslator, make_parser_pos_translator
from .placeholders import make_placeholder_config
from .source import LinePosition
from .template_utils import PartPosition


@pytest.fixture(scope="module")
def ph_config():
    return make_placeholder_config()


@pytest.fixture(scope="module")
def t_maker(ph_config) -> Callable[[Template], ParserPositionTranslator]:
    def maker(template: Template) -> ParserPositionTranslator:
        return make_parser_pos_translator(template=template, config=ph_config)

    return maker


class TestParserPosToPartPos:
    def test_offset(self, t_maker):
        ppt = t_maker(t"a*")
        pos = ppt.translate(LinePosition(line=1, offset=1))
        assert pos.index == 0 and pos.offset == 1

    def test_line(self, t_maker):
        pos = t_maker(t"ab\n*").translate(LinePosition(line=2, offset=0))
        assert pos.index == 0 and pos.offset == 3

    def test_interpolation_after(self, t_maker):
        translator = t_maker(t"ab\nc{0}d*")
        offset = len("".join(("c", translator.config.make_placeholder(0), "d")))
        pos = translator.translate(LinePosition(line=2, offset=offset))
        assert pos == PartPosition(index=2, offset=1)

    def test_interpolation_right_after(self, t_maker):
        translator = t_maker(t"ab\nc{0}*")
        offset = len("".join(("c", translator.config.make_placeholder(0))))
        pos = translator.translate(LinePosition(line=2, offset=offset))
        assert pos == PartPosition(index=2, offset=0)

    def test_interpolation_end_of_line_start_of_line(self, t_maker):
        translator = t_maker(t"""ab\nc{0}a\n
""")
        pos = translator.translate(LinePosition(line=3, offset=0))
        assert pos == PartPosition(index=2, offset=2)
