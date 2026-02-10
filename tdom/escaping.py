import re

from markupsafe import escape as markup_escape

from .protocols import HasHTMLDunder


escape_html_text = markup_escape  # unify api for test of project


GT = "&gt;"
LT = "&lt;"


def escape_html_comment(text: str, allow_markup: bool = False) -> str:
    """Escape text injected into an HTML comment."""
    if not text:
        return text
    elif allow_markup and isinstance(text, HasHTMLDunder):
        return text.__html__()
    elif not allow_markup and type(text) is not str:
        # text manipulation triggers regular html escapes on Markup
        text = str(text)

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


# @NOTE: We use a group to preserve the case of the tagname, ie. StylE -> StylE
# @NOTE: Rawstrings are needed for the groupname to resolve correctly
# otherwise the slash must be escaped twice again.
STYLE_RES = ((re.compile("</(?P<tagname>style)>", re.I | re.A), LT + r"/\g<tagname>>"),)


def escape_html_style(text: str, allow_markup: bool = False) -> str:
    """Escape text injected into an HTML style element."""
    if allow_markup and isinstance(text, HasHTMLDunder):
        return text.__html__()
    for matche_re, replace_text in STYLE_RES:
        text = re.sub(matche_re, replace_text, text)
    return text


SCRIPT_RES = (
    # @NOTE: Slashes are unescaped inside `repl` text in ADDITION to
    # python's default unescaping.  So for a regular python str() you need
    # `//` but for a python str() in res.sub(*, repl, *) you need 4 slashes,
    # `////`, but we can use a rawstring to only need 2 slashes, ie. `//`.
    # in order to get a single slash out the other side.
    # @NOTE: We use a group to preserve the case of the tagname,
    # ie. ScripT->ScripT.
    # @NOTE: Rawstrings are also needed for the groupname to resolve correctly
    # otherwise the slash must be escaped twice again.
    (re.compile("<!--", re.I | re.A), r"\\x3c!--"),
    (re.compile("<(?P<tagname>script)", re.I | re.A), r"\\x3c\g<tagname>"),
    (re.compile("</(?P<tagname>script)", re.I | re.A), r"\\x3c/\g<tagname>"),
)


def escape_html_script(text: str, allow_markup: bool = False) -> str:
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
    if allow_markup and isinstance(text, HasHTMLDunder):
        return text.__html__()
    for match_re, replace_text in SCRIPT_RES:
        text = re.sub(match_re, replace_text, text)
    return text
