from markupsafe import Markup

from .escaping import (
    escape_html_comment,
    escape_html_script,
    escape_html_style,
    escape_html_text,
)


def test_escape_html_text() -> None:
    assert escape_html_text("<div>") == "&lt;div&gt;"


def test_escape_html_comment_empty() -> None:
    assert escape_html_comment("") == ""


def test_escape_html_comment_no_special() -> None:
    assert escape_html_comment("This is a comment.") == "This is a comment."


def test_escape_html_comment_starts_with_gt() -> None:
    assert escape_html_comment(">This is a comment.") == "&gt;This is a comment."


def test_escape_html_comment_starts_with_dash_gt() -> None:
    assert escape_html_comment("->This is a comment.") == "-&gt;This is a comment."


def test_escape_html_comment_contains_special_strings() -> None:
    input_text = "This is <!-- a comment --> with --!> special strings."
    expected_output = "This is &lt;!-- a comment --&gt; with --!&gt; special strings."
    assert escape_html_comment(input_text) == expected_output


def test_escape_html_comment_ends_with_lt_dash() -> None:
    assert escape_html_comment("This is a comment<!-") == "This is a comment&lt;!-"


def test_escape_html_comment_markup() -> None:
    input_text = "-->"
    escaped_text = "--&gt;"
    out = escape_html_comment(Markup(input_text), allow_markup=False)
    assert out != input_text and out == escaped_text
    out = escape_html_comment(Markup(input_text), allow_markup=True)
    assert out == input_text and out != escaped_text


def test_escape_html_style() -> None:
    input_text = "body { color: red; }</style> p { font-SIZE: 12px; }</STYLE>"
    expected_output = (
        "body { color: red; }&lt;/style> p { font-SIZE: 12px; }&lt;/STYLE>"
    )
    assert escape_html_style(input_text) == expected_output


def test_escape_html_style_markup() -> None:
    input_text = "</STYLE>"
    escaped_text = "&lt;/STYLE>"
    out = escape_html_style(Markup(input_text), allow_markup=False)
    assert out != input_text and out == escaped_text
    out = escape_html_style(Markup(input_text), allow_markup=True)
    assert out == input_text and out != escaped_text


def test_escape_html_script() -> None:
    input_text = "<!-- <script>var a = 1;</script> </SCRIPT>"
    expected_output = "\\x3c!-- \\x3cscript>var a = 1;\\x3c/script> \\x3c/SCRIPT>"
    assert escape_html_script(input_text) == expected_output
    # Smoketest that escaping is working and we are not just escaping back to the same value.
    for text in ("<script", "</script", "<!--"):
        assert escape_html_script(text) != text


def test_escape_html_script_markup() -> None:
    input_text = "<script>"
    escaped_text = "\\x3cscript>"
    out = escape_html_script(Markup(input_text), allow_markup=False)
    assert out != input_text and out == escaped_text
    out = escape_html_script(Markup(input_text), allow_markup=True)
    assert out == input_text and out != escaped_text
