from .escaping import escape_html_comment, escape_html_script, escape_html_style


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


def test_escape_html_style() -> None:
    input_text = "body { color: red; }</style> p { font-SIZE: 12px; }</STYLE>"
    expected_output = (
        "body { color: red; }&lt;/style> p { font-SIZE: 12px; }&lt;/style>"
    )
    assert escape_html_style(input_text) == expected_output


def test_escape_html_script() -> None:
    input_text = "<!-- <script>var a = 1;</script> </SCRIPT>"
    expected_output = "\x3c!-- \x3cscript>var a = 1;\x3c/script> </script>"
    assert escape_html_script(input_text) == expected_output
