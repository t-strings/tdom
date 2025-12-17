import re

from markupsafe import escape as markup_escape

escape_html_text = markup_escape  # unify api for test of project


GT = "&gt;"
LT = "&lt;"


def escape_html_comment(text: str) -> str:
    """Escape text injected into an HTML comment."""
    if not text:
        return text
    # - text must not start with the string ">"
    if text[0] == ">":
        text = GT + text[1:]

    # - nor start with the string "->"
    if text[:2] == "->":
        text = "-" + GT + text[2:]

    # - nor contain the strings "<!--", "-->", or "--!>"
    text = text.replace("<!--", LT + "!--")
    text = text.replace("-->", "--" + GT)
    text = text.replace("--!>", "--!" + GT)

    # - nor end with the string "<!-".
    if text[-3:] == "<!-":
        text = text[:-3] + LT + "!-"

    return text


STYLE_RES = ((re.compile("</style>", re.I | re.A), LT + "/style>"),)


def escape_html_style(text: str) -> str:
    """Escape text injected into an HTML style element."""
    for matche_re, replace_text in STYLE_RES:
        text = re.sub(matche_re, replace_text, text)
    return text


SCRIPT_RES = (
    (re.compile("<!--", re.I | re.A), "\x3c!--"),
    (re.compile("<script", re.I | re.A), "\x3cscript"),
    (re.compile("</script", re.I | re.A), "\x3c/script"),
)


def escape_html_script(text: str) -> str:
    """
    Escape text injected into an HTML script element.

    https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements

    (from link) The easiest and safest way to avoid the rather strange restrictions
    described in this section is to always escape an ASCII case-insensitive
    match for:
    - "<!--" as "\x3c!--"
    - "<script" as "\x3cscript"
    - "</script" as "\x3c/script"`
    """
    for match_re, replace_text in SCRIPT_RES:
        text = re.sub(match_re, replace_text, text)
    return text
