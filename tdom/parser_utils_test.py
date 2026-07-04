from string.templatelib import Template

import pytest

from .parser_utils import ParserPositionTranslator, make_parser_pos_translator
from .placeholders import PlaceholderConfig, make_placeholder_config
from .source import LinePosition
from .template_utils import PartPosition


@pytest.fixture(scope="module")
def ph_config():
    return make_placeholder_config()


def make_ppt(template: Template, config: PlaceholderConfig) -> ParserPositionTranslator:
    "Just a shorthand function."
    return make_parser_pos_translator(template=template, config=config)


class TestParserPosToPartPos:
    def test_offset(self, ph_config):
        ppt = make_ppt(t"a*", ph_config)
        assert ppt.translate(LinePosition(line=1, offset=1)) == PartPosition(
            index=0, offset=1
        )

    def test_line(self, ph_config):
        ppt = make_ppt(t"ab\n*", ph_config)
        assert ppt.translate(LinePosition(line=2, offset=0)) == PartPosition(
            index=0, offset=3
        )

    def test_interpolation_after(self, ph_config):
        ppt = make_ppt(t"ab\nc{0}d*", ph_config)
        offset = len("".join(("c", ph_config.make_placeholder(0), "d")))
        assert ppt.translate(LinePosition(line=2, offset=offset)) == PartPosition(
            index=2, offset=1
        )

    def test_interpolation_right_after(self, ph_config):
        ppt = make_ppt(t"ab\nc{0}*", ph_config)
        offset = len("".join(("c", ph_config.make_placeholder(0))))
        assert ppt.translate(LinePosition(line=2, offset=offset)) == PartPosition(
            index=2, offset=0
        )

    def test_interpolation_end_of_line_start_of_line(self, ph_config):
        ppt = make_ppt(
            t"""ab\nc{0}a\n
""",
            ph_config,
        )
        assert ppt.translate(LinePosition(line=3, offset=0)) == PartPosition(
            index=2, offset=2
        )
