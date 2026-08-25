from string.templatelib import Template

import pytest

from .source import LinePosition, SourceReader, template_repr
from .template_utils import PartPosition, TemplateRef


class TestSourceReader:
    """
    Top-level tests for SourceReader class.

    More in depth tests are handled in more specialized test.
    """

    def test_values_match(self):
        def comp() -> Template:
            return t""

        reader = SourceReader(template=t"<{comp}></{comp}>{'content'}")
        assert reader.values_match(0, 1)
        assert not reader.values_match(0, 2)

    def test_ref_to_repr(self):
        reader = SourceReader(template=t"a{'b'!s}c")
        assert (
            reader.ref_to_repr(TemplateRef(strings=("A", ""), i_start=0)) == "A{'b'!s}"
        )

    def test_make_template_pos_msg(self):
        reader = SourceReader(template=t"<div>{'content'}</div>")
        msg = reader.make_template_pos_msg(source_pos=PartPosition(s_index=0, offset=1))
        assert msg == "line 1 offset 1"

    def test_make_interpolation_repr(self):
        reader = SourceReader(template=t"<div>{'content'}</div>")
        assert reader.make_interpolation_repr(0) == "{'content'}"

    def test_to_template_pos(self):
        reader = SourceReader(template=t"<div>{'content'}</div>")
        assert reader.to_template_pos(
            PartPosition(s_index=0, offset=len("<div>"))
        ) == LinePosition(line=1, offset=len("<div>"))


class TestTemplateRepresentation:
    # whitespace is part of test
    # fmt: off
    @pytest.mark.parametrize(
        ("t", "result"),
        (
            (t"<div>{15!s:formatspec}</div>", "<div>{15!s:formatspec}</div>"),
            (t"<div>{15:formatspec}</div>", "<div>{15:formatspec}</div>"),
            (t"<div>{15!s}</div>", "<div>{15!s}</div>"),
            (t"<div>{15}</div>", "<div>{15}</div>"),
            (t"{15}", "{15}"),
            (t"", ""),
            (t"A{0}B{1}{2}C", "A{0}B{1}{2}C"),
            (t"ABC", "ABC"),
            (t"""<div>
</div>""", """<div>\n</div>"""),
            (t"""{'''
'''}""", """{'''\n'''}"""),
        )
    )
    def test_repr(self, t: Template, result: str):
        assert template_repr(t) == result
    # fmt: on


class TestToTemplatePosition:
    def test_origin(self):
        t = t"<div>{'content'}</div>"
        reader = SourceReader(template=t)
        source_pos = PartPosition(s_index=0, offset=0)
        assert reader.to_template_pos(source_pos) == LinePosition(line=1, offset=0)

    def test_offset_no_lines(self):
        t = t"<div>{'content'}</div>"
        reader = SourceReader(template=t)
        source_pos = PartPosition(s_index=0, offset=len(t.strings[0]))
        assert reader.to_template_pos(source_pos) == LinePosition(
            line=1, offset=len(t.strings[0])
        )

    def test_offset_full_interpolation(self):
        t = t"<div>{''!s:lower}</div>"  # conversion and formatspec
        reader = SourceReader(template=t)
        source_pos = PartPosition(s_index=1, offset=0)
        assert reader.to_template_pos(source_pos) == LinePosition(
            line=1, offset=len('<div>{""!s:lower}')
        )

    def test_line(self):
        # whitespace is part of test
        # fmt: off
        t = t"""<div>
{"content"}</div>"""
        # fmt: on
        reader = SourceReader(template=t)
        source_pos = PartPosition(s_index=1, offset=0)
        assert reader.to_template_pos(source_pos) == LinePosition(
            line=2, offset=len('{"content"}')
        )

    def test_line_in_interpolation(self):
        # whitespace is part of test
        # fmt: off
        t = t"""<div>
{'''
content
'''}</div>"""
        # fmt: on
        reader = SourceReader(template=t)
        source_pos = PartPosition(s_index=1, offset=0)
        assert reader.to_template_pos(source_pos) == LinePosition(
            line=4, offset=len("'''}")
        )
