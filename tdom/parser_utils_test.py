from string.templatelib import Template

import pytest

from .parser_utils import (
    ParserPositionTranslator,
    make_parser_pos_translator,
)
from .placeholders import PlaceholderConfig, make_placeholder_config
from .source import LinePosition
from .template_utils import PartPosition


@pytest.fixture(scope="module")
def ph_config():
    return make_placeholder_config()


def make_ppt(template: Template, config: PlaceholderConfig) -> ParserPositionTranslator:
    "Just a shorthand function."
    return make_parser_pos_translator(template=template, config=config)


class TestParserPositionTranslator:
    def test_normalize_to_absolute_offset(self, ph_config):
        ppt = make_ppt(t"ab\ncd\n", ph_config)

        assert ppt.validate_raw_parser_pos(LinePosition(1, 0)) == 0
        assert ppt.validate_raw_parser_pos(LinePosition(1, 2)) == 2
        assert ppt.validate_raw_parser_pos(LinePosition(2, 0)) == 3
        assert ppt.validate_raw_parser_pos(LinePosition(2, 2)) == 5
        assert ppt.validate_raw_parser_pos(LinePosition(3, 0)) == 6

    def test_case_nontailing_string_ends_with_newline(self, ph_config):
        ppt = make_ppt(t"a\n{0}b", ph_config)
        assert ppt.translate(LinePosition(line=2, offset=0)) == PartPosition(
            index=1, offset=0
        ), """This could also be considered PartPosition(index=1, offset=0)
        but either way should work. """
        assert ppt.translate(
            LinePosition(line=2, offset=len(ph_config.make_placeholder(0)))
        ) == PartPosition(
            index=2, offset=0
        ), """This must be the start of the following string because we can't
        know the offset of the actual interpolation content. Ie. It cannot be
        index=1 with "some" offset."""

    def test_case_tailing_string_starts_with_newline(self, ph_config):
        ppt = make_ppt(t"a{0}\nb", ph_config)
        assert ppt.translate(LinePosition(line=2, offset=0)) == PartPosition(
            index=2, offset=1
        ), "line 2 should be inside the tailing string"
        assert ppt.translate(
            LinePosition(line=1, offset=1 + len(ph_config.make_placeholder(0)))
        ) == PartPosition(index=2, offset=0), (
            "end of line 1 should be inside the tailing string?"
        )

    def test_case_interpolation_without_lines(self, ph_config):
        ppt = make_ppt(t"a{0}b", ph_config)
        assert ppt.translate(LinePosition(line=1, offset=1)) == PartPosition(
            index=1, offset=0
        ), "end of the head string is the start of the interpolation"
        assert ppt.translate(
            LinePosition(line=1, offset=1 + len(ph_config.make_placeholder(0)))
        ) == PartPosition(index=2, offset=0), (
            "the end of the interpolation is the start of the tailing string"
        )
        assert ppt.translate(
            LinePosition(line=1, offset=1 + len(ph_config.make_placeholder(0)) + 1)
        ) == PartPosition(index=2, offset=1), (
            "the end of the tailing string remains the end."
        )

    def test_case_consecutive_interpolations(self, ph_config):
        ppt = make_ppt(t"{0}{1}", ph_config)
        placeholder_length = len(ph_config.make_placeholder(0))

        assert ppt.translate(LinePosition(1, 0)) == PartPosition(1, 0)
        assert ppt.translate(LinePosition(1, placeholder_length)) == PartPosition(2, 0)
        assert ppt.translate(LinePosition(1, 2 * placeholder_length)) == PartPosition(
            4, 0
        )

    def test_offset_without_line(self, ph_config):
        ppt = make_ppt(t"a*", ph_config)
        assert ppt.translate(LinePosition(line=1, offset=1)) == PartPosition(
            index=0, offset=1
        ), "the offset matches up without lines"
        assert ppt.translate(LinePosition(line=1, offset=2)) == PartPosition(
            index=0, offset=2
        ), "end of line is end of string"
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            # only 0, 1 and 2 are valid offsets for line 1
            _ = ppt.translate(LinePosition(line=1, offset=3)) == PartPosition(
                index=0, offset=3
            )

    def test_offset_with_line(self, ph_config):
        ppt = make_ppt(t"ab\n*", ph_config)
        assert ppt.translate(LinePosition(line=2, offset=0)) == PartPosition(
            index=0, offset=3
        ), "2nd line starts at offset in the head string"
        assert ppt.translate(LinePosition(line=1, offset=2)) == PartPosition(
            index=0, offset=2
        ), "end of 1st line is offset to NL"
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            # only 0, 1 and 2 are valid offsets for line 1
            _ = ppt.translate(LinePosition(line=1, offset=3))

    def test_offset_with_line_in_middle_part(self, ph_config):
        ppt = make_ppt(t"a\nb{0}cd\ne{1}\nfe", ph_config)
        assert ppt.translate(
            LinePosition(line=2, offset=1 + len(ph_config.make_placeholder(0)) + 2)
        ) == PartPosition(index=2, offset=2)

    def test_empty_strings(self, ph_config):
        ppt = make_ppt(t"{0}", ph_config)
        assert ppt.translate(LinePosition(line=1, offset=0)) == PartPosition(
            index=1, offset=0
        ), "start of head string is start of interpolation"
        assert ppt.translate(
            LinePosition(line=1, offset=len(ph_config.make_placeholder(0)))
        ) == PartPosition(index=2, offset=0), (
            "end of interpolation is start of tail string"
        )
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            # Cannot go past end of the template.
            _ = ppt.translate(
                LinePosition(line=1, offset=len(ph_config.make_placeholder(0)) + 1)
            )

    def test_empty_string(self, ph_config):
        ppt = make_ppt(t"", ph_config)
        assert ppt.translate(LinePosition(line=1, offset=0)) == PartPosition(
            index=0, offset=0
        )
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            # Cannot go past end of the template.
            _ = ppt.translate(LinePosition(line=1, offset=1))

    def test_empty_line(self, ph_config):
        ppt = make_ppt(t"\n", ph_config)
        assert ppt.translate(LinePosition(line=1, offset=0)) == PartPosition(
            index=0, offset=0
        )
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            # line 1 is empty, cannot offset anything
            _ = ppt.translate(LinePosition(line=1, offset=1))
        assert ppt.translate(LinePosition(line=2, offset=0)) == PartPosition(
            index=0, offset=1
        ), "To skip over empty line just skip over newline"
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            # line 2 is empty, cannot offset anything
            _ = ppt.translate(LinePosition(line=2, offset=1))

    def test_bad_parser_pos_check_bounds(self, ph_config):
        ppt = make_ppt(t"abc\ndef", ph_config)

        with pytest.raises(ValueError, match="Line does not exist"):
            _ = ppt.translate(LinePosition(line=3, offset=0))
        with pytest.raises(ValueError, match="Unreachable line number"):
            _ = ppt.translate(LinePosition(line=0, offset=0))
        with pytest.raises(ValueError, match="Unreachable offset"):
            _ = ppt.translate(LinePosition(line=1, offset=-1))
        with pytest.raises(ValueError, match="Unreachable offset"):
            _ = ppt.translate(LinePosition(line=2, offset=-1))
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            _ = ppt.translate(LinePosition(line=1, offset=100))
        with pytest.raises(ValueError, match="Offset exceeds reachable"):
            _ = ppt.translate(LinePosition(line=2, offset=100))

    def test_bad_parser_pos_cannot_offset_interpolation(self, ph_config):
        ppt = make_ppt(t"abc\n{0}def", ph_config)

        with pytest.raises(
            ValueError,
            match="Invalid part position, interpolations are not divisible, offset must be 0.",
        ):
            _ = ppt.translate(LinePosition(line=2, offset=1))
        with pytest.raises(
            ValueError,
            match="Invalid part position, interpolations are not divisible, offset must be 0.",
        ):
            _ = ppt.translate(
                LinePosition(line=2, offset=len(ph_config.make_placeholder(0)) - 1)
            )
