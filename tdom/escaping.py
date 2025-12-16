import re

from markupsafe import escape as markup_escape

escape_html_text = markup_escape  # unify api for test of project


def escape_html_comment(text):
    """Escape text injected into an HTML comment."""
    GT = "&gt;"
    LT = "&lt;"

    if not text:
        return text
    # - text must not start with the string ">"
    if text[0] == ">":
        text = GT + text[1:]

    # - nor start with the string "->"
    if text[:2] == "->":
        text = "-" + GT + text[2:]

    # - nor contain the strings "<!--", "-->", or "--!>"
    index = text.find("<!--")
    if index != -1:
        text = text[:index] + LT + text[index + 1]
    index = text.find("-->")
    if index != -1:
        text = text[: index + 2] + GT + text[index + 3]
    index = text.find("--!>")
    if index != -1:
        text = text[: index + 3] + GT + text[index + 4]

    # - nor end with the string "<!-".
    if text[-3:] == "<!-":
        text = text[:-3] + LT + "!-"

    return text


def escape_html_style(text):
    LT = "&lt;"
    close_str = "</style>"
    close_str_re = re.compile(close_str, re.I | re.A)
    replace_str = LT + close_str[1:]
    return re.sub(close_str_re, replace_str, text)


def escape_html_script(text):
    """
    https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements

    (from link) The easiest and safest way to avoid the rather strange restrictions
    described in this section is to always escape an ASCII case-insensitive
    match for:
    - "<!--" as "\x3c!--"
    - "<script" as "\x3cscript"
    - "</script" as "\x3c/script"`
    """
    match_to_replace = (
        (re.compile("<!--", re.I | re.A), "\x3c!--"),
        (re.compile("<script", re.I | re.A), "\x3cscript"),
        (re.compile("</script", re.I | re.A), "\x3c/script"),
    )
    for match_re, replace_text in match_to_replace:
        text = re.sub(match_re, replace_text, text)
    return text
