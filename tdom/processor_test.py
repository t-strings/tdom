import datetime
import typing as t
from dataclasses import dataclass
from string.templatelib import Template
from itertools import product, chain
from collections.abc import Callable

import pytest
from markupsafe import Markup, escape as markupsafe_escape

from .processor import (
    to_html as to_html_str,
    prep_component_kwargs,
    processor_service_factory,
    make_ctx,
)
from .callables import get_callable_info
from .escaping import escape_html_text


from .nodes.processor import to_node


def to_node_str(*args, **kwargs):
    """Proxy to to_node but then strify the result to match non-node processor."""
    return str(to_node(*args, **kwargs))


processor_api = processor_service_factory(slash_void=True, uppercase_doctype=True)


def to_html_str_no_cache(*args, **kwargs):
    return processor_api.process_template(*args, **kwargs)


PROCESSORS = [to_html_str, to_node_str, to_html_str_no_cache]
" List of processor functions to test against. "

# --------------------------------------------------------------------------
# Basic HTML parsing tests
# --------------------------------------------------------------------------


#
# Text
#
@pytest.mark.parametrize("to_html", PROCESSORS)
class TestBareTemplate:
    def test_empty(self, to_html):
        assert to_html(t"") == ""

    def test_text_literal(self, to_html):
        assert to_html(t"Hello, world!") == "Hello, world!"

    def test_text_singleton(self, to_html):
        greeting = "Hello, Alice!"
        assert to_html(t"{greeting}", make_ctx(parent_tag="div")) == "Hello, Alice!"
        assert to_html(t"{greeting}", make_ctx(parent_tag="script")) == "Hello, Alice!"
        assert to_html(t"{greeting}", make_ctx(parent_tag="style")) == "Hello, Alice!"
        assert (
            to_html(t"{greeting}", make_ctx(parent_tag="textarea")) == "Hello, Alice!"
        )
        assert to_html(t"{greeting}", make_ctx(parent_tag="title")) == "Hello, Alice!"

    def test_text_singleton_without_parent(self, to_html):
        greeting = "</script>"
        with pytest.raises(NotImplementedError):
            # Explicitly set the parent tag as None.
            ctx = make_ctx(parent_tag=None, ns="html")
            _ = to_html(t"{greeting}", assume_ctx=ctx)

    def test_text_singleton_explicit_parent_script(self, to_html):
        greeting = "</script>"
        res = to_html(t"{greeting}", assume_ctx=make_ctx(parent_tag="script"))
        assert res == "\\x3c/script>"
        assert res != "</script>"

    def test_text_singleton_explicit_parent_div(self, to_html):
        greeting = "</div>"
        res = to_html(t"{greeting}", assume_ctx=make_ctx(parent_tag="div"))
        assert res == "&lt;/div&gt;"
        assert res != "</div>"

    def test_text_template(self, to_html):
        name = "Alice"
        assert (
            to_html(t"Hello, {name}!", assume_ctx=make_ctx(parent_tag="div"))
            == "Hello, Alice!"
        )

    def test_text_template_escaping(self, to_html):
        name = "Alice & Bob"
        assert (
            to_html(t"Hello, {name}!", assume_ctx=make_ctx(parent_tag="div"))
            == "Hello, Alice &amp; Bob!"
        )

    def test_parse_entities_are_escaped_no_parent_tag(self, to_html):
        res = to_html(t"&lt;/p&gt;")
        assert res == "&lt;/p&gt;", "Default to standard escaping."


@pytest.mark.parametrize("to_html", PROCESSORS)
class LiteralHTML:
    """Text is returned as is by __html__."""

    def __init__(self, text):
        self.text = text

    def __html__(self):
        # In a real app, this would come from a sanitizer or trusted source
        return self.text


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestComment:
    def test_literal(self, to_html):
        assert to_html(t"<!--This is a comment-->") == "<!--This is a comment-->"

    #
    # Singleton / Exact Match
    #
    def test_singleton_str(self, to_html):
        text = "This is a comment"
        assert to_html(t"<!--{text}-->") == "<!--This is a comment-->"

    def test_singleton_object(self, to_html):
        assert to_html(t"<!--{0}-->") == "<!--0-->"

    def test_singleton_none(self, to_html):
        assert to_html(t"<!--{None}-->") == "<!---->"

    def test_singleton_has_dunder_html(self, to_html):
        content = LiteralHTML("-->")
        assert to_html(t"<!--{content}-->") == "<!---->-->", (
            "DO NOT DO THIS! This is just an advanced escape hatch."
        )

    def test_singleton_escaping(self, to_html):
        text = "-->comment"
        assert to_html(t"<!--{text}-->") == "<!----&gt;comment-->"

    #
    # Templated -- literal text mixed with interpolation(s)
    #
    def test_templated_str(self, to_html):
        text = "comment"
        assert to_html(t"<!--This is a {text}-->") == "<!--This is a comment-->"

    def test_templated_object(self, to_html):
        assert to_html(t"<!--This is a {0}-->") == "<!--This is a 0-->"

    def test_templated_none(self, to_html):
        assert to_html(t"<!--This is a {None}-->") == "<!--This is a -->"

    def test_templated_has_dunder_html_error(self, to_html):
        """Objects with __html__ are not processed with literal text or other interpolations."""
        text = LiteralHTML("in a comment")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--This is a {text}-->")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--{None}{text}-->")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--This is a {Markup('Also check specialized cls.')}-->")

    def test_templated_multiple_interpolations(self, to_html):
        text = "comment"
        assert (
            to_html(t"<!--This is a {text} with {0} and {None}-->")
            == "<!--This is a comment with 0 and -->"
        )

    def test_templated_escaping(self, to_html):
        # @TODO: There doesn't seem to be a way to properly escape this
        # so we just use an entity to break the special closing string
        # even though it won't be actually unescaped by anything. There
        # might be something better for this.
        text = "-->comment"
        assert to_html(t"<!--This is a {text}-->") == "<!--This is a --&gt;comment-->"

    def test_not_supported__recursive_template_error(self, to_html):
        text_t = t"comment"
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--{text_t}-->")

    def test_not_supported_recursive_iterable_error(self, to_html):
        texts = ["This", "is", "a", "comment"]
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--{texts}-->")


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestDocumentType:
    def test_literal(self, to_html):
        assert to_html(t"<!doctype html>") == "<!DOCTYPE html>"


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestVoidElementLiteral:
    def test_void(self, to_html):
        assert to_html(t"<br>") == "<br />"

    def test_void_self_closed(self, to_html):
        assert to_html(t"<br />") == "<br />"

    def test_void_mixed_closing(self, to_html):
        assert to_html(t"<br>Is this content?<br />") == "<br />Is this content?<br />"

    def test_chain_of_void_elements(self, to_html):
        # Make sure our handling of CPython issue #69445 is reasonable.
        assert (
            to_html(t"<br><hr><img src='image.png' /><br /><hr>")
            == '<br /><hr /><img src="image.png" /><br /><hr />'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestNormalTextElementLiteral:
    def test_empty(self, to_html):
        assert to_html(t"<div></div>") == "<div></div>"

    def test_with_text(self, to_html):
        assert to_html(t"<p>Hello, world!</p>") == "<p>Hello, world!</p>"

    def test_nested_elements(self, to_html):
        assert (
            to_html(t"<div><p>Hello</p><p>World</p></div>")
            == "<div><p>Hello</p><p>World</p></div>"
        )

    def test_entities_are_escaped(self, to_html):
        """Literal entities interpreted by parser but escaped in output."""
        res = to_html(t"<p>&lt;/p&gt;</p>")
        assert res == "<p>&lt;/p&gt;</p>", res


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestNormalTextElementDynamic:
    def test_singleton_None(self, to_html):
        assert to_html(t"<p>{None}</p>") == "<p></p>"

    def test_singleton_str(self, to_html):
        name = "Alice"
        assert to_html(t"<p>{name}</p>") == "<p>Alice</p>"

    def test_singleton_object(self, to_html):
        assert to_html(t"<p>{0}</p>") == "<p>0</p>"

    def test_singleton_has_dunder_html(self, to_html):
        content = LiteralHTML("<em>Alright!</em>")
        assert to_html(t"<p>{content}</p>") == "<p><em>Alright!</em></p>"

    def test_singleton_simple_template(self, to_html):
        name = "Alice"
        text_t = t"Hi {name}"
        assert to_html(t"<p>{text_t}</p>") == "<p>Hi Alice</p>"

    def test_singleton_simple_iterable(self, to_html):
        strs = ["Strings", "...", "Yeah!", "Rock", "...", "Yeah!"]
        assert to_html(t"<p>{strs}</p>") == "<p>Strings...Yeah!Rock...Yeah!</p>"

    def test_singleton_escaping(self, to_html):
        text = '''<>&'"'''
        assert to_html(t"<p>{text}</p>") == "<p>&lt;&gt;&amp;&#39;&#34;</p>"

    def test_templated_None(self, to_html):
        assert to_html(t"<p>Response: {None}.</p>") == "<p>Response: .</p>"

    def test_templated_str(self, to_html):
        name = "Alice"
        assert to_html(t"<p>Response: {name}.</p>") == "<p>Response: Alice.</p>"

    def test_templated_object(self, to_html):
        assert to_html(t"<p>Response: {0}.</p>") == "<p>Response: 0.</p>"

    def test_templated_has_dunder_html(self, to_html):
        text = LiteralHTML("<em>Alright!</em>")
        assert (
            to_html(t"<p>Response: {text}.</p>")
            == "<p>Response: <em>Alright!</em>.</p>"
        )

    def test_templated_simple_template(self, to_html):
        name = "Alice"
        text_t = t"Hi {name}"
        assert to_html(t"<p>Response: {text_t}.</p>") == "<p>Response: Hi Alice.</p>"

    def test_templated_simple_iterable(self, to_html):
        strs = ["Strings", "...", "Yeah!", "Rock", "...", "Yeah!"]
        assert (
            to_html(t"<p>Response: {strs}.</p>")
            == "<p>Response: Strings...Yeah!Rock...Yeah!.</p>"
        )

    def test_templated_escaping(self, to_html):
        text = '''<>&'"'''
        assert (
            to_html(t"<p>Response: {text}.</p>")
            == "<p>Response: &lt;&gt;&amp;&#39;&#34;.</p>"
        )

    def test_templated_escaping_in_literals(self, to_html):
        text = "This text is fine"
        assert (
            to_html(t"<p>The literal has &lt; in it: {text}.</p>")
            == "<p>The literal has &lt; in it: This text is fine.</p>"
        )

    def test_iterable_of_templates(self, to_html):
        items = ["Apple", "Banana", "Cherry"]
        assert (
            to_html(t"<ul>{[t'<li>{item}</li>' for item in items]}</ul>")
            == "<ul><li>Apple</li><li>Banana</li><li>Cherry</li></ul>"
        )

    def test_iterable_of_templates_of_iterable_of_templates(self, to_html):
        outer = ["fruit", "more fruit"]
        inner = ["apple", "banana", "cherry"]
        inner_items = [t"<li>{item}</li>" for item in inner]
        outer_items = [
            t"<li>{category}<ul>{inner_items}</ul></li>" for category in outer
        ]
        assert (
            to_html(t"<ul>{outer_items}</ul>")
            == "<ul><li>fruit<ul><li>apple</li><li>banana</li><li>cherry</li></ul></li><li>more fruit<ul><li>apple</li><li>banana</li><li>cherry</li></ul></li></ul>"
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestRawTextElementLiteral:
    def test_script_empty(self, to_html):
        assert to_html(t"<script></script>") == "<script></script>"

    def test_style_empty(self, to_html):
        assert to_html(t"<style></style>") == "<style></style>"

    def test_script_with_content(self, to_html):
        assert to_html(t"<script>var x = 1;</script>") == "<script>var x = 1;</script>"

    def test_style_with_content(self, to_html):
        # @NOTE: Double {{ and }} to avoid t-string interpolation.
        assert (
            to_html(t"<style>.red {{ color: red; }}</style>")
            == "<style>.red { color: red; }</style>"
        )

    def test_script_with_content_escaped_in_normal_text(self, to_html):
        # @NOTE: Double {{ and }} to avoid t-string interpolation.
        assert (
            to_html(
                t"<script>function CompareNumbers(a, b) {{ return a < b; }}</script>"
            )
            == "<script>function CompareNumbers(a, b) { return a < b; }</script>"
        ), "The < should not be escaped."

    def test_style_with_content_escaped_in_normal_text(self, to_html):
        # @NOTE: Double {{ and }} to avoid t-string interpolation.
        assert (
            to_html(t"<style>section > h4 {{ background-color: red; }}</style>")
            == "<style>section > h4 { background-color: red; }</style>"
        ), "The > should not be escaped."

    def test_not_supported_recursive_template_error(self, to_html):
        text_t = t"comment"
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--{text_t}-->")

    def test_not_supported_recursive_iterable_error(self, to_html):
        texts = ["This", "is", "a", "comment"]
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<!--{texts}-->")


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestEscapableRawTextElementLiteral:
    def test_title_empty(self, to_html):
        assert to_html(t"<title></title>") == "<title></title>"

    def test_textarea_empty(self, to_html):
        assert to_html(t"<textarea></textarea>") == "<textarea></textarea>"

    def test_title_with_content(self, to_html):
        assert to_html(t"<title>Content</title>") == "<title>Content</title>"

    def test_textarea_with_content(self, to_html):
        assert (
            to_html(t"<textarea>Content</textarea>") == "<textarea>Content</textarea>"
        )

    def test_title_with_escapable_content(self, to_html):
        assert (
            to_html(t"<title>Are t-strings > everything?</title>")
            == "<title>Are t-strings &gt; everything?</title>"
        ), "The > can be escaped in this content type."

    def test_textarea_with_escapable_content(self, to_html):
        assert (
            to_html(t"<textarea><p>Welcome To TDOM</p></textarea>")
            == "<textarea>&lt;p&gt;Welcome To TDOM&lt;/p&gt;</textarea>"
        ), "The p tags can be escaped in this content type."


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestRawTextScriptDynamic:
    def test_singleton_none(self, to_html):
        assert to_html(t"<script>{None}</script>") == "<script></script>"

    def test_singleton_str(self, to_html):
        content = "var x = 1;"
        assert to_html(t"<script>{content}</script>") == "<script>var x = 1;</script>"

    def test_singleton_object(self, to_html):
        content = 0
        assert to_html(t"<script>{content}</script>") == "<script>0</script>"

    def test_singleton_has_dunder_html_pitfall(self, to_html):
        # @TODO: We should probably put some double override to prevent this by accident.
        # Or just disable this and if people want to do this then put the
        # content in a SCRIPT and inject the whole thing with a __html__?
        content = LiteralHTML("</script>")
        assert to_html(t"<script>{content}</script>") == "<script></script></script>", (
            "DO NOT DO THIS! This is just an advanced escape hatch! Use a data attribute and parseJSON!"
        )

    def test_singleton_escaping(self, to_html):
        content = "</script>"
        script_t = t"<script>{content}</script>"
        bad_output = script_t.strings[0] + content + script_t.strings[1]
        assert to_html(script_t) == "<script>\\x3c/script></script>"
        assert to_html(script_t) != bad_output, "Sanity check."

    def test_templated_none(self, to_html):
        assert (
            to_html(t"<script>var x = 1;{None};</script>")
            == "<script>var x = 1;;</script>"
        )

    def test_templated_str(self, to_html):
        content = "var x = 1"
        assert (
            to_html(t"<script>var x = 0;{content};</script>")
            == "<script>var x = 0;var x = 1;</script>"
        )

    def test_templated_object(self, to_html):
        content = 0
        assert (
            to_html(t"<script>var x = {content};</script>")
            == "<script>var x = 0;</script>"
        )

    def test_templated_has_dunder_html(self, to_html):
        content = LiteralHTML("anything")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<script>var x = 1;{content}</script>")

    def test_templated_escaping(self, to_html):
        content = "</script>"
        script_t = t"<script>var x = '{content}';</script>"
        bad_output = script_t.strings[0] + content + script_t.strings[1]
        assert to_html(script_t) == "<script>var x = '\\x3c/script>';</script>"
        assert to_html(script_t) != bad_output, "Sanity check."

    def test_templated_multiple_interpolations(self, to_html):
        assert (
            to_html(t"<script>var x = {1}; var y = {2};</script>")
            == "<script>var x = 1; var y = 2;</script>"
        )

    def test_not_supported_recursive_template_error(self, to_html):
        text_t = t"script"
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<script>{text_t}</script>")

    def test_not_supported_recursive_iterable_error(self, to_html):
        texts = ["This", "is", "a", "script"]
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<script>{texts}</script>")


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestRawTextStyleDynamic:
    def test_singleton_none(self, to_html):
        assert to_html(t"<style>{None}</style>") == "<style></style>"

    def test_singleton_str(self, to_html):
        content = "div { background-color: red; }"
        assert (
            to_html(t"<style>{content}</style>")
            == "<style>div { background-color: red; }</style>"
        )

    def test_singleton_object(self, to_html):
        content = 0
        assert to_html(t"<style>{content}</style>") == "<style>0</style>"

    def test_singleton_has_dunder_html_pitfall(self, to_html):
        # @TODO: We should probably put some double override to prevent this by accident.
        # Or just disable this and if people want to do this then put the
        # content in a STYLE and inject the whole thing with a __html__?
        content = LiteralHTML("</style>")
        assert to_html(t"<style>{content}</style>") == "<style></style></style>", (
            "DO NOT DO THIS! This is just an advanced escape hatch!"
        )

    def test_singleton_escaping(self, to_html):
        content = "</style>"
        style_t = t"<style>{content}</style>"
        bad_output = style_t.strings[0] + content + style_t.strings[1]
        assert to_html(style_t) == "<style>&lt;/style></style>"
        assert to_html(style_t) != bad_output, "Sanity check."

    def test_templated_none(self, to_html):
        assert (
            to_html(t"<style>h1 {{ background-color: red; }}{None}</style>")
            == "<style>h1 { background-color: red; }</style>"
        )

    def test_templated_str(self, to_html):
        content = " h2 { background-color: blue; }"
        assert (
            to_html(t"<style>h1 {{ background-color: red; }}{content}</style>")
            == "<style>h1 { background-color: red; } h2 { background-color: blue; }</style>"
        )

    def test_templated_object(self, to_html):
        padding_right = 0
        assert (
            to_html(t"<style>h1 {{ padding-right: {padding_right}px; }}</style>")
            == "<style>h1 { padding-right: 0px; }</style>"
        )

    def test_templated_has_dunder_html(self, to_html):
        content = LiteralHTML("anything")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<style>h1 {{ color: red; }};{content}</style>")

    def test_templated_escaping(self, to_html):
        content = "</style>"
        style_t = t"<style>div {{ background-color: red; }} {content}</style>"
        bad_output = style_t.strings[0] + content + style_t.strings[1]
        assert (
            to_html(style_t)
            == "<style>div { background-color: red; } &lt;/style></style>"
        )
        assert to_html(style_t) != bad_output, "Sanity check."

    def test_templated_multiple_interpolations(self, to_html):
        assert (
            to_html(
                t"<style>h1 {{ background-color: {'red'}; }} h2 {{ background-color: {'blue'}; }}</style>"
            )
            == "<style>h1 { background-color: red; } h2 { background-color: blue; }</style>"
        )

    def test_not_supported_recursive_template_error(self, to_html):
        text_t = t"style"
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<style>{text_t}</style>")

    def test_not_supported_recursive_iterable_error(self, to_html):
        texts = ["This", "is", "a", "style"]
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<style>{texts}</style>")


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestEscapableRawTextTitleDynamic:
    def test_singleton_none(self, to_html):
        assert to_html(t"<title>{None}</title>") == "<title></title>"

    def test_singleton_str(self, to_html):
        content = "Welcome To TDOM"
        assert to_html(t"<title>{content}</title>") == "<title>Welcome To TDOM</title>"

    def test_singleton_object(self, to_html):
        content = 0
        assert to_html(t"<title>{content}</title>") == "<title>0</title>"

    def test_singleton_has_dunder_html_pitfall(self, to_html):
        # @TODO: We should probably put some double override to prevent this by accident.
        content = LiteralHTML("</title>")
        assert to_html(t"<title>{content}</title>") == "<title></title></title>", (
            "DO NOT DO THIS! This is just an advanced escape hatch!"
        )

    def test_singleton_escaping(self, to_html):
        content = "</title>"
        assert to_html(t"<title>{content}</title>") == "<title>&lt;/title&gt;</title>"

    def test_templated_none(self, to_html):
        assert (
            to_html(t"<title>A great story about: {None}</title>")
            == "<title>A great story about: </title>"
        )

    def test_templated_str(self, to_html):
        content = "TDOM"
        assert (
            to_html(t"<title>A great story about: {content}</title>")
            == "<title>A great story about: TDOM</title>"
        )

    def test_templated_object(self, to_html):
        content = 0
        assert (
            to_html(t"<title>A great number: {content}</title>")
            == "<title>A great number: 0</title>"
        )

    def test_templated_has_dunder_html(self, to_html):
        content = LiteralHTML("No")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<title>Literal html?: {content}</title>")

    def test_templated_escaping(self, to_html):
        content = "</title>"
        assert (
            to_html(t"<title>The end tag: {content}.</title>")
            == "<title>The end tag: &lt;/title&gt;.</title>"
        )

    def test_templated_multiple_interpolations(self, to_html):
        assert (
            to_html(t"<title>The number {0} is less than {1}.</title>")
            == "<title>The number 0 is less than 1.</title>"
        )

    def test_not_supported_recursive_template_error(self, to_html):
        text_t = t"title"
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<title>{text_t}</title>")

    def test_not_supported_recursive_iterable_error(self, to_html):
        texts = ["This", "is", "a", "title"]
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<title>{texts}</title>")


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestEscapableRawTextTextareaDynamic:
    def test_singleton_none(self, to_html):
        assert to_html(t"<textarea>{None}</textarea>") == "<textarea></textarea>"

    def test_singleton_str(self, to_html):
        content = "Welcome To TDOM"
        assert (
            to_html(t"<textarea>{content}</textarea>")
            == "<textarea>Welcome To TDOM</textarea>"
        )

    def test_singleton_object(self, to_html):
        content = 0
        assert to_html(t"<textarea>{content}</textarea>") == "<textarea>0</textarea>"

    def test_singleton_has_dunder_html_pitfall(self, to_html):
        # @TODO: We should probably put some double override to prevent this by accident.
        content = LiteralHTML("</textarea>")
        assert (
            to_html(t"<textarea>{content}</textarea>")
            == "<textarea></textarea></textarea>"
        ), "DO NOT DO THIS! This is just an advanced escape hatch!"

    def test_singleton_escaping(self, to_html):
        content = "</textarea>"
        assert (
            to_html(t"<textarea>{content}</textarea>")
            == "<textarea>&lt;/textarea&gt;</textarea>"
        )

    def test_templated_none(self, to_html):
        assert (
            to_html(t"<textarea>A great story about: {None}</textarea>")
            == "<textarea>A great story about: </textarea>"
        )

    def test_templated_str(self, to_html):
        content = "TDOM"
        assert (
            to_html(t"<textarea>A great story about: {content}</textarea>")
            == "<textarea>A great story about: TDOM</textarea>"
        )

    def test_templated_object(self, to_html):
        content = 0
        assert (
            to_html(t"<textarea>A great number: {content}</textarea>")
            == "<textarea>A great number: 0</textarea>"
        )

    def test_templated_has_dunder_html(self, to_html):
        content = LiteralHTML("No")
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<textarea>Literal html?: {content}</textarea>")

    def test_templated_multiple_interpolations(self, to_html):
        assert (
            to_html(t"<textarea>The number {0} is less than {1}.</textarea>")
            == "<textarea>The number 0 is less than 1.</textarea>"
        )

    def test_templated_escaping(self, to_html):
        content = "</textarea>"
        assert (
            to_html(t"<textarea>The end tag: {content}.</textarea>")
            == "<textarea>The end tag: &lt;/textarea&gt;.</textarea>"
        )

    def test_not_supported_recursive_template_error(self, to_html):
        text_t = t"textarea"
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<textarea>{text_t}</textarea>")

    def test_not_supported_recursive_iterable_error(self, to_html):
        texts = ["This", "is", "a", "textarea"]
        with pytest.raises(ValueError, match="not supported"):
            _ = to_html(t"<textarea>{texts}</textarea>")


class Convertible:
    def __str__(self):
        return "string"

    def __repr__(self):
        return "repr"


def test_convertible_fixture():
    """Make sure test fixture is working correctly."""
    c = Convertible()
    assert f"{c!s}" == "string"
    assert f"{c!r}" == "repr"


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestInterpolationConversion:
    def test_str(self, to_html):
        c = Convertible()
        assert to_html(t"<div>{c!s}</div>") == "<div>string</div>"

    def test_repr(self, to_html):
        c = Convertible()
        assert to_html(t"<div>{c!r}</div>") == "<div>repr</div>"

    def test_ascii(self, to_html):
        assert (
            to_html(t"<div>{'😊'!a}</div>")
            == f"<div>{escape_html_text(ascii('😊'))}</div>"
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestInterpolationFormatSpec:
    def test_safe(self, to_html):
        raw_content = "<u>underlined</u>"
        assert (
            to_html(t"<p>This is {raw_content:safe} text.</p>")
            == "<p>This is <u>underlined</u> text.</p>"
        )

    def test_unsafe(self, to_html):
        supposedly_safe = Markup("<i>italic</i>")
        assert (
            to_html(t"<p>This is {supposedly_safe:unsafe} text.</p>")
            == "<p>This is &lt;i&gt;italic&lt;/i&gt; text.</p>"
        )

    def test_callback(self, to_html):
        def get_value():
            return "dynamic"

        assert (
            to_html(t"<p>The value is {get_value:callback}.</p>")
            == "<p>The value is dynamic.</p>"
        )

    def test_callback_nonzero_callable_error(self, to_html):
        def add(a, b):
            return a + b

        assert add(1, 2) == 3, "Make sure fixture could work..."

        with pytest.raises(TypeError):
            _ = to_html(t"<p>The sum is {add:callback}.</p>")


# --------------------------------------------------------------------------
# Conditional rendering and control flow
# --------------------------------------------------------------------------


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestUsagePatterns:
    def test_conditional_rendering_with_if_else(self, to_html):
        is_logged_in = True
        user_profile = t"<span>Welcome, User!</span>"
        login_prompt = t"<a href='/login'>Please log in</a>"
        assert (
            to_html(t"<div>{user_profile if is_logged_in else login_prompt}</div>")
            == "<div><span>Welcome, User!</span></div>"
        )

        is_logged_in = False
        assert (
            to_html(t"<div>{user_profile if is_logged_in else login_prompt}</div>")
            == '<div><a href="/login">Please log in</a></div>'
        )


# --------------------------------------------------------------------------
# Attributes
# --------------------------------------------------------------------------
@pytest.mark.parametrize("to_html", PROCESSORS)
class TestLiteralAttribute:
    """Test literal (non-dynamic) attributes."""

    def test_literal_attrs(self, to_html):
        assert (
            to_html(
                (
                    t"<a "
                    t" id=example_link"  # no quotes required if value has no surrounding whitespace
                    t" autofocus"  # bare / boolean
                    t' title=""'  # empty attribute
                    t' href="https://example.com" target="_blank"'
                    t"></a>"
                )
            )
            == '<a id="example_link" autofocus title="" href="https://example.com" target="_blank"></a>'
        )

    def test_literal_attr_escaped(self, to_html):
        assert (
            to_html(t'<a title="&lt;&gt;&amp;&#39;&#34;"></a>')
            == '<a title="&lt;&gt;&amp;&#39;&#34;"></a>'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestInterpolatedAttribute:
    """Test interpolated attributes, entire value is an exact interpolation."""

    def test_interpolated_attr(self, to_html):
        url = "https://example.com/"
        assert to_html(t'<a href="{url}"></a>') == '<a href="https://example.com/"></a>'

    def test_interpolated_attr_escaped(self, to_html):
        url = 'https://example.com/?q="test"&lang=en'
        assert (
            to_html(t'<a href="{url}"></a>')
            == '<a href="https://example.com/?q=&#34;test&#34;&amp;lang=en"></a>'
        )

    def test_interpolated_attr_unquoted(self, to_html):
        id = "roquefort"
        assert to_html(t"<div id={id}></div>") == '<div id="roquefort"></div>'

    def test_interpolated_attr_true(self, to_html):
        disabled = True
        assert (
            to_html(t"<button disabled={disabled}></button>")
            == "<button disabled></button>"
        )

    def test_interpolated_attr_false(self, to_html):
        disabled = False
        assert to_html(t"<button disabled={disabled}></button>") == "<button></button>"

    def test_interpolated_attr_none(self, to_html):
        disabled = None
        assert to_html(t"<button disabled={disabled}></button>") == "<button></button>"

    def test_interpolate_attr_empty_string(self, to_html):
        assert to_html(t'<div title=""></div>') == '<div title=""></div>'


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestSpreadAttribute:
    """Test spread attributes."""

    def test_spread_attr(self, to_html):
        attrs = {"href": "https://example.com/", "target": "_blank"}
        assert (
            to_html(t"<a {attrs}></a>")
            == '<a href="https://example.com/" target="_blank"></a>'
        )

    def test_spread_attr_none(self, to_html):
        attrs = None
        assert to_html(t"<a {attrs}></a>") == "<a></a>"

    def test_spread_attr_type_errors(self, to_html):
        for attrs in (0, [], (), False, True):
            with pytest.raises(TypeError):
                _ = to_html(t"<a {attrs}></a>")


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestTemplatedAttribute:
    def test_templated_attr_mixed_interpolations_start_end_and_nest(self, to_html):
        left, middle, right = 1, 3, 5
        prefix, suffix = t'<div data-range="', t'"></div>'
        # Check interpolations at start, middle and/or end of templated attr
        # or a combination of those to make sure text is not getting dropped.
        for left_part, middle_part, right_part in product(
            (t"{left}", Template(str(left))),
            (t"{middle}", Template(str(middle))),
            (t"{right}", Template(str(right))),
        ):
            test_t = (
                prefix + left_part + t"-" + middle_part + t"-" + right_part + suffix
            )
            assert to_html(test_t) == '<div data-range="1-3-5"></div>'

    def test_templated_attr_no_quotes(self, to_html):
        start = 1
        end = 5
        assert (
            to_html(t"<div data-range={start}-{end}></div>")
            == '<div data-range="1-5"></div>'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestAttributeMerging:
    def test_attr_merge_disjoint_interpolated_attr_spread_attr(self, to_html):
        attrs = {"href": "https://example.com/", "id": "link1"}
        target = "_blank"
        assert (
            to_html(t"<a {attrs} target={target}></a>")
            == '<a href="https://example.com/" id="link1" target="_blank"></a>'
        )

    def test_attr_merge_overlapping_spread_attrs(self, to_html):
        attrs1 = {"href": "https://example.com/", "id": "overwrtten"}
        attrs2 = {"target": "_blank", "id": "link1"}
        assert (
            to_html(t"<a {attrs1} {attrs2}></a>")
            == '<a href="https://example.com/" target="_blank" id="link1"></a>'
        )

    def test_attr_merge_replace_literal_attr_str_str(self, to_html):
        assert (
            to_html(t'<div title="default" {dict(title="fresh")}></div>')
            == '<div title="fresh"></div>'
        )

    def test_attr_merge_replace_literal_attr_str_true(self, to_html):
        assert (
            to_html(t'<div title="default" {dict(title=True)}></div>')
            == "<div title></div>"
        )

    def test_attr_merge_replace_literal_attr_true_str(self, to_html):
        assert (
            to_html(t"<div title {dict(title='fresh')}></div>")
            == '<div title="fresh"></div>'
        )

    def test_attr_merge_remove_literal_attr_str_none(self, to_html):
        assert (
            to_html(t'<div title="default" {dict(title=None)}></div>') == "<div></div>"
        )

    def test_attr_merge_remove_literal_attr_true_none(self, to_html):
        assert to_html(t"<div title {dict(title=None)}></div>") == "<div></div>"

    def test_attr_merge_other_literal_attr_intact(self, to_html):
        assert (
            to_html(t'<img title="default" {dict(alt="fresh")}>')
            == '<img title="default" alt="fresh" />'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestSpecialDataAttribute:
    """Special data attribute handling."""

    def test_interpolated_data_attributes(self, to_html):
        data = {
            "user-id": 123,
            "role": "admin",
            "wild": True,
            "false": False,
            "none": None,
        }
        assert (
            to_html(t"<div data={data}>User Info</div>")
            == '<div data-user-id="123" data-role="admin" data-wild>User Info</div>'
        )

    def test_data_attr_toggle_to_str(self, to_html):
        for res in [
            to_html(t"<div data-selected data={dict(selected='yes')}></div>"),
            to_html(t'<div data-selected="no" data={dict(selected="yes")}></div>'),
        ]:
            assert res == '<div data-selected="yes"></div>'

    def test_data_attr_toggle_to_true(self, to_html):
        res = to_html(t'<div data-selected="yes" data={dict(selected=True)}></div>')
        assert res == "<div data-selected></div>"

    def test_data_attr_unrelated_unaffected(self, to_html):
        res = to_html(t"<div data-selected data={dict(active=True)}></div>")
        assert res == "<div data-selected data-active></div>"

    def test_data_attr_templated_error(self, to_html):
        data1 = {"user-id": "user-123"}
        data2 = {"role": "admin"}
        with pytest.raises(TypeError):
            _ = to_html(t'<div data="{data1} {data2}"></div>')

    def test_data_attr_none(self, to_html):
        button_data = None
        res = to_html(t"<button data={button_data}>X</button>")
        assert res == "<button>X</button>"

    def test_data_attr_errors(self, to_html):
        for v in [False, [], (), 0, "data?"]:
            with pytest.raises(TypeError):
                _ = to_html(t"<button data={v}>X</button>")

    def test_data_literal_attr_bypass(self, to_html):
        # Trigger overall attribute resolution with an unrelated interpolated attr.
        res = to_html(t'<p data="passthru" id={"resolved"}></p>')
        assert res == '<p data="passthru" id="resolved"></p>', (
            "A single literal attribute should not trigger data expansion."
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestSpecialAriaAttribute:
    """Special aria attribute handling."""

    def test_aria_templated_attr_error(self, to_html):
        aria1 = {"label": "close"}
        aria2 = {"hidden": "true"}
        with pytest.raises(TypeError):
            _ = to_html(t'<div aria="{aria1} {aria2}"></div>')

    def test_aria_interpolated_attr_dict(self, to_html):
        aria = {"label": "Close", "hidden": True, "another": False, "more": None}
        res = to_html(t"<button aria={aria}>X</button>")
        assert (
            res
            == '<button aria-label="Close" aria-hidden="true" aria-another="false">X</button>'
        )

    def test_aria_interpolate_attr_none(self, to_html):
        button_aria = None
        res = to_html(t"<button aria={button_aria}>X</button>")
        assert res == "<button>X</button>"

    def test_aria_attr_errors(self, to_html):
        for v in [False, [], (), 0, "aria?"]:
            with pytest.raises(TypeError):
                _ = to_html(t"<button aria={v}>X</button>")

    def test_aria_literal_attr_bypass(self, to_html):
        # Trigger overall attribute resolution with an unrelated interpolated attr.
        res = to_html(t'<p aria="passthru" id={"resolved"}></p>')
        assert res == '<p aria="passthru" id="resolved"></p>', (
            "A single literal attribute should not trigger aria expansion."
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestSpecialClassAttribute:
    """Special class attribute handling."""

    def test_interpolated_class_attribute(self, to_html):
        class_list = ["btn", "btn-primary", "one two", None]
        class_dict = {"active": True, "btn-secondary": False}
        class_str = "blue"
        class_space_sep_str = "green yellow"
        class_none = None
        class_empty_list = []
        class_empty_dict = {}
        button_t = (
            t"<button "
            t' class="red" class={class_list} class={class_dict}'
            t" class={class_empty_list} class={class_empty_dict}"  # ignored
            t" class={class_none}"  # ignored
            t" class={class_str} class={class_space_sep_str}"
            t" >Click me</button>"
        )
        res = to_html(button_t)
        assert (
            res
            == '<button class="red btn btn-primary one two active blue green yellow">Click me</button>'
        )

    def test_interpolated_class_attribute_with_multiple_placeholders(self, to_html):
        classes1 = ["btn", "btn-primary"]
        classes2 = [False and "disabled", None, {"active": True}]
        res = to_html(t'<button class="{classes1} {classes2}">Click me</button>')
        # CONSIDER: Is this what we want? Currently, when we have multiple
        # placeholders in a single attribute, we treat it as a string attribute.
        assert (
            res
            == f'<button class="{escape_html_text(str(classes1))} {escape_html_text(str(classes2))}">Click me</button>'
        ), (
            "Interpolations that are not exact, or singletons, are instead interpreted as templates and therefore these dictionaries are strified."
        )

    def test_interpolated_attribute_spread_with_class_attribute(self, to_html):
        attrs = {"id": "button1", "class": ["btn", "btn-primary"]}
        res = to_html(t"<button {attrs}>Click me</button>")
        assert res == '<button id="button1" class="btn btn-primary">Click me</button>'

    def test_class_literal_attr_bypass(self, to_html):
        # Trigger overall attribute resolution with an unrelated interpolated attr.
        res = to_html(t'<p class="red red" id={"veryred"}></p>')
        assert res == '<p class="red red" id="veryred"></p>', (
            "A single literal attribute should not trigger class accumulator."
        )

    def test_class_none_ignored(self, to_html):
        class_item = None
        res = to_html(t"<p class={class_item}></p>")
        assert res == "<p></p>"
        # Also ignored inside a sequence.
        res = to_html(t"<p class={[class_item]}></p>")
        assert res == "<p></p>"

    def test_class_type_errors(self, to_html):
        for class_item in (False, True, 0):
            with pytest.raises(TypeError):
                _ = to_html(t"<p class={class_item}></p>")
            with pytest.raises(TypeError):
                _ = to_html(t"<p class={[class_item]}></p>")

    def test_class_merge_literals(self, to_html):
        res = to_html(t'<p class="red" class="blue"></p>')
        assert res == '<p class="red blue"></p>'

    def test_class_merge_literal_then_interpolation(self, to_html):
        class_item = "blue"
        res = to_html(t'<p class="red" class="{[class_item]}"></p>')
        assert res == '<p class="red blue"></p>'


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestSpecialStyleAttribute:
    """Special style attribute handling."""

    def test_style_literal_attr_passthru(self, to_html):
        p_id = "para1"  # non-literal attribute to cause attr resolution
        res = to_html(t'<p style="color: red" id={p_id}>Warning!</p>')
        assert res == '<p style="color: red" id="para1">Warning!</p>'

    def test_style_in_interpolated_attr(self, to_html):
        styles = {"color": "red", "font-weight": "bold", "font-size": "16px"}
        res = to_html(t"<p style={styles}>Warning!</p>")
        assert (
            res
            == '<p style="color: red; font-weight: bold; font-size: 16px">Warning!</p>'
        )

    def test_style_in_templated_attr(self, to_html):
        color = "red"
        res = to_html(t'<p style="color: {color}">Warning!</p>')
        assert res == '<p style="color: red">Warning!</p>'

    def test_style_in_spread_attr(self, to_html):
        attrs = {"style": {"color": "red"}}
        res = to_html(t"<p {attrs}>Warning!</p>")
        assert res == '<p style="color: red">Warning!</p>'

    def test_style_merged_from_all_attrs(self, to_html):
        attrs = dict(style="font-size: 15px")
        style = {"font-weight": "bold"}
        color = "red"
        res = to_html(
            t'<p style="font-family: serif" style="color: {color}" style={style} {attrs}></p>'
        )
        assert (
            res
            == '<p style="font-family: serif; color: red; font-weight: bold; font-size: 15px"></p>'
        )

    def test_style_override_left_to_right(self, to_html):
        suffix = t"></p>"
        parts = [
            (t'<p style="color: red"', "color: red"),
            (t" style={dict(color='blue')}", "color: blue"),
            (t' style="color: {"green"}"', "color: green"),
            (t""" {dict(style=dict(color="yellow"))}""", "color: yellow"),
        ]
        for index in range(len(parts)):
            expected_style = parts[index][1]
            t = sum([part[0] for part in parts[: index + 1]], t"") + suffix
            res = to_html(t)
            assert res == f'<p style="{expected_style}"></p>'

    def test_interpolated_style_attribute_multiple_placeholders(self, to_html):
        styles1 = {"color": "red"}
        styles2 = {"font-weight": "bold"}
        # CONSIDER: Is this what we want? Currently, when we have multiple
        # placeholders in a single attribute, we treat it as a string attribute
        # which produces an invalid style attribute.
        with pytest.raises(ValueError):
            _ = to_html(t"<p style='{styles1} {styles2}'>Warning!</p>")

    def test_interpolated_style_attribute_merged(self, to_html):
        styles1 = {"color": "red"}
        styles2 = {"font-weight": "bold"}
        res = to_html(t"<p style={styles1} style={styles2}>Warning!</p>")
        assert res == '<p style="color: red; font-weight: bold">Warning!</p>'

    def test_interpolated_style_attribute_merged_override(self, to_html):
        styles1 = {"color": "red", "font-weight": "normal"}
        styles2 = {"font-weight": "bold"}
        res = to_html(t"<p style={styles1} style={styles2}>Warning!</p>")
        assert res == '<p style="color: red; font-weight: bold">Warning!</p>'

    def test_style_attribute_str(self, to_html):
        styles = "color: red; font-weight: bold;"
        res = to_html(t"<p style={styles}>Warning!</p>")
        assert res == '<p style="color: red; font-weight: bold">Warning!</p>'

    def test_style_attribute_non_str_non_dict(self, to_html):
        with pytest.raises(TypeError):
            styles = [1, 2]
            _ = to_html(t"<p style={styles}>Warning!</p>")

    def test_style_literal_attr_bypass(self, to_html):
        # Trigger overall attribute resolution with an unrelated interpolated attr.
        res = to_html(t'<p style="invalid;invalid:" id={"resolved"}></p>')
        assert res == '<p style="invalid;invalid:" id="resolved"></p>', (
            "A single literal attribute should bypass style accumulator."
        )

    def test_style_none(self, to_html):
        styles = None
        res = to_html(t"<p style={styles}></p>")
        assert res == "<p></p>"


class TestPrepComponentKwargs:
    def test_named(self):
        def InputElement(size=10, type="text"):
            pass

        callable_info = get_callable_info(InputElement)
        assert prep_component_kwargs(callable_info, {"size": 20}, system_kwargs={}) == {
            "size": 20
        }
        assert prep_component_kwargs(
            callable_info, {"type": "email"}, system_kwargs={}
        ) == {"type": "email"}
        assert prep_component_kwargs(callable_info, {}, system_kwargs={}) == {}

    @pytest.mark.skip("Should we just ignore unused user-specified kwargs?")
    def test_unused_kwargs(self):
        def InputElement(size=10, type="text"):
            pass

        callable_info = get_callable_info(InputElement)
        with pytest.raises(ValueError):
            assert (
                prep_component_kwargs(callable_info, {"type2": 15}, system_kwargs={})
                == {}
            )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestFunctionComponent:
    @staticmethod
    def FunctionComponent(
        children: Template, first: str, second: int, third_arg: str, **attrs: t.Any
    ) -> Template:
        # Ensure type correctness of props at runtime for testing purposes
        assert isinstance(first, str)
        assert isinstance(second, int)
        assert isinstance(third_arg, str)
        new_attrs = {
            "id": third_arg,
            "data": {"first": first, "second": second},
            **attrs,
        }
        return t"<div {new_attrs}>Component: {children}</div>"

    def test_with_children(self, to_html):
        res = to_html(
            t'<{self.FunctionComponent} first=1 second={99} third-arg="comp1" class="my-comp">Hello, Component!</{self.FunctionComponent}>'
        )
        assert (
            res
            == '<div id="comp1" data-first="1" data-second="99" class="my-comp">Component: Hello, Component!</div>'
        )

    def test_with_no_children(self, to_html):
        """Same test, but the caller didn't provide any children."""
        res = to_html(
            t'<{self.FunctionComponent} first=1 second={99} third-arg="comp1" class="my-comp" />'
        )
        assert (
            res
            == '<div id="comp1" data-first="1" data-second="99" class="my-comp">Component: </div>'
        )

    def test_missing_props_error(self, to_html):
        with pytest.raises(TypeError):
            _ = to_html(
                t"<{self.FunctionComponent}>Missing props</{self.FunctionComponent}>"
            )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestFunctionComponentNoChildren:
    @staticmethod
    def FunctionComponentNoChildren(
        first: str, second: int, third_arg: str
    ) -> Template:
        # Ensure type correctness of props at runtime for testing purposes
        assert isinstance(first, str)
        assert isinstance(second, int)
        assert isinstance(third_arg, str)
        new_attrs = {
            "id": third_arg,
            "data": {"first": first, "second": second},
        }
        return t"<div {new_attrs}>Component: ignore children</div>"

    def test_interpolated_template_component_ignore_children(self, to_html):
        res = to_html(
            t'<{self.FunctionComponentNoChildren} first=1 second={99} third-arg="comp1">Hello, Component!</{self.FunctionComponentNoChildren}>'
        )
        assert (
            res
            == '<div id="comp1" data-first="1" data-second="99">Component: ignore children</div>'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestFunctionComponentKeywordArgs:
    @staticmethod
    def FunctionComponentKeywordArgs(first: str, **attrs: t.Any) -> Template:
        # Ensure type correctness of props at runtime for testing purposes
        assert isinstance(first, str)
        assert "children" in attrs
        children = attrs.pop("children")
        new_attrs = {"data-first": first, **attrs}
        return t"<div {new_attrs}>Component with kwargs: {children}</div>"

    def test_children_always_passed_via_kwargs(self, to_html):
        res = to_html(
            t'<{self.FunctionComponentKeywordArgs} first="value" extra="info">Child content</{self.FunctionComponentKeywordArgs}>'
        )
        assert (
            res
            == '<div data-first="value" extra="info">Component with kwargs: Child content</div>'
        )

    def test_children_always_passed_via_kwargs_even_when_empty(self, to_html):
        res = to_html(
            t'<{self.FunctionComponentKeywordArgs} first="value" extra="info" />'
        )
        assert (
            res == '<div data-first="value" extra="info">Component with kwargs: </div>'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestComponentSpecialUsage:
    @staticmethod
    def ColumnsComponent() -> Template:
        return t"""<td>Column 1</td><td>Column 2</td>"""

    def test_fragment_from_component(self, to_html):
        # This test assumes that if a component returns a template that parses
        # into multiple root elements, they are treated as a fragment.
        res = to_html(t"<table><tr><{self.ColumnsComponent} /></tr></table>")
        assert res == "<table><tr><td>Column 1</td><td>Column 2</td></tr></table>"

    def test_component_passed_as_attr_value(self, to_html):
        def Wrapper(
            children: Template, sub_component: t.Callable, **attrs: t.Any
        ) -> Template:
            return t"<{sub_component} {attrs}>{children}</{sub_component}>"

        res = to_html(
            t'<{Wrapper} sub-component={TestFunctionComponent.FunctionComponent} class="wrapped" first=1 second={99} third-arg="comp1"><p>Inside wrapper</p></{Wrapper}>'
        )
        assert (
            res
            == '<div id="comp1" data-first="1" data-second="99" class="wrapped">Component: <p>Inside wrapper</p></div>'
        )

    def test_nested_component_gh23(self, to_html):
        # @DESIGN: Do we need this?  Should we recommend an alternative?
        # See https://github.com/t-strings/tdom/issues/23 for context
        def Header() -> Template:
            return t"{'Hello World'}"

        res = to_html(t"<{Header} />", assume_ctx=make_ctx(parent_tag="div"))
        assert res == "Hello World"


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestClassComponent:
    @dataclass
    class ClassComponent:
        """Example class-based component."""

        user_name: str
        image_url: str
        children: Template
        homepage: str = "#"

        def __call__(self) -> Template:
            return (
                t"<div class='avatar'>"
                t"<a href={self.homepage}>"
                t"<img src='{self.image_url}' alt='{f'Avatar of {self.user_name}'}' />"
                t"</a>"
                t"<span>{self.user_name}</span>"
                t"{self.children}"
                t"</div>"
            )

    def test_class_component_implicit_invocation_with_children(self, to_html):
        res = to_html(
            t"<{self.ClassComponent} user-name='Alice' image-url='https://example.com/alice.png'>Fun times!</{self.ClassComponent}>"
        )
        assert (
            res
            == '<div class="avatar"><a href="#"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span>Fun times!</div>'
        )

    def test_class_component_direct_invocation(self, to_html):
        avatar = self.ClassComponent(
            user_name="Alice",
            image_url="https://example.com/alice.png",
            homepage="https://example.com/users/alice",
            children=t"",  # Children is required so we set it to an empty template.
        )
        res = to_html(t"<{avatar} />")
        assert (
            res
            == '<div class="avatar"><a href="https://example.com/users/alice"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span></div>'
        )

    @dataclass
    class ClassComponentNoChildren:
        """Example class-based component that does not ask for children."""

        user_name: str
        image_url: str
        homepage: str = "#"

        def __call__(self) -> Template:
            return (
                t"<div class='avatar'>"
                t"<a href={self.homepage}>"
                t"<img src='{self.image_url}' alt='{f'Avatar of {self.user_name}'}' />"
                t"</a>"
                t"<span>{self.user_name}</span>"
                t"ignore children"
                t"</div>"
            )

    def test_implicit_invocation_ignore_children(self, to_html):
        res = to_html(
            t"<{self.ClassComponentNoChildren} user-name='Alice' image-url='https://example.com/alice.png'>Fun times!</{self.ClassComponentNoChildren}>"
        )
        assert (
            res
            == '<div class="avatar"><a href="#"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span>ignore children</div>'
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
def test_attribute_type_component(to_html):
    def AttributeTypeComponent(
        data_int: int,
        data_true: bool,
        data_false: bool,
        data_none: None,
        data_float: float,
        data_dt: datetime.datetime,
        **kws: dict[str, object | None],
    ) -> Template:
        """Component to test that we don't incorrectly convert attribute types."""
        assert isinstance(data_int, int)
        assert data_true is True
        assert data_false is False
        assert data_none is None
        assert isinstance(data_float, float)
        assert isinstance(data_dt, datetime.datetime)
        for kw, v_type in [
            ("spread_true", True),
            ("spread_false", False),
            ("spread_int", int),
            ("spread_none", None),
            ("spread_float", float),
            ("spread_dt", datetime.datetime),
            ("spread_dict", dict),
            ("spread_list", list),
        ]:
            if v_type in (True, False, None):
                assert kw in kws and kws[kw] is v_type, (
                    f"{kw} should be {v_type} but got {kws=}"
                )
            else:
                assert kw in kws and isinstance(kws[kw], v_type), (
                    f"{kw} should instance of {v_type} but got {kws=}"
                )
        return t"Looks good!"

    an_int: int = 42
    a_true: bool = True
    a_false: bool = False
    a_none: None = None
    a_float: float = 3.14
    a_dt: datetime.datetime = datetime.datetime(2024, 1, 1, 12, 0, 0)
    spread_attrs: dict[str, object | None] = {
        "spread_true": True,
        "spread_false": False,
        "spread_none": None,
        "spread_int": 0,
        "spread_float": 0.0,
        "spread_dt": datetime.datetime(2024, 1, 1, 12, 0, 1),
        "spread_dict": dict(),
        "spread_list": ["eggs", "milk"],
    }
    res = to_html(
        t"<{AttributeTypeComponent} data-int={an_int} data-true={a_true} "
        t"data-false={a_false} data-none={a_none} data-float={a_float} "
        t"data-dt={a_dt} {spread_attrs}/>"
    )
    assert res == "Looks good!"


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestComponentErrors:
    def test_component_non_callable_fails(self, to_html):
        with pytest.raises(TypeError):
            _ = to_html(t"<{'not a function'} />")

    def test_component_requiring_positional_arg_fails(self, to_html):
        def RequiresPositional(whoops: int, /) -> Template:  # pragma: no cover
            return t"<p>Positional arg: {whoops}</p>"

        with pytest.raises(TypeError):
            _ = to_html(t"<{RequiresPositional} />")

    def test_mismatched_component_closing_tag_fails(self, to_html):
        def OpenTag(children: Template) -> Template:
            return t"<div>open</div>"

        def CloseTag(children: Template) -> Template:
            return t"<div>close</div>"

        with pytest.raises(TypeError):
            _ = to_html(t"<{OpenTag}>Hello</{CloseTag}>")


@pytest.mark.parametrize("to_html", PROCESSORS)
def test_integration_basic(to_html):
    comment_text = "comment is not literal"
    interpolated_class = "red"
    text_in_element = "text is not literal"
    templated = "not literal"
    spread_attrs = {"data-on": True}
    markup_content = Markup("<div>safe</div>")

    def WrapperComponent(children):
        return t"<div>{children}</div>"

    smoke_t = t"""<!doctype html>
<html>
<body>
<!-- literal -->
<span attr="literal">literal</span>
<!-- {comment_text} -->
<span>{text_in_element}</span>
<span attr="literal" class={interpolated_class} title="is {templated}" {spread_attrs}>{text_in_element}</span>
<{WrapperComponent}><span>comp body</span></{WrapperComponent}>
{markup_content}
</body>
</html>"""
    smoke_str = """<!DOCTYPE html>
<html>
<body>
<!-- literal -->
<span attr="literal">literal</span>
<!-- comment is not literal -->
<span>text is not literal</span>
<span attr="literal" title="is not literal" data-on class="red">text is not literal</span>
<div><span>comp body</span></div>
<div>safe</div>
</body>
</html>"""
    assert to_html(smoke_t) == smoke_str


def struct_repr(st):
    """Breakdown Templates into comparable parts for test verification."""
    return st.strings, tuple(
        [
            (i.value, i.expression, i.conversion, i.format_spec)
            for i in st.interpolations
        ]
    )


'''
@pytest.mark.skip("Come back to this.")
def test_process_template_internal_cache(to_html):
    """Test that cache and non-cache both generally work as expected."""
    """
    sample_t = t'<div>{"content"}</div>'
    sample_diff_t = t'<div>{"diffcontent"}</div>'
    alt_t = t'<span>{"content"}</span>'
    process_api = processor_service_factory()
    cached_process_api = cached_processor_service_factory()
    # Technically this could be the superclass which doesn't have cached method.
    assert isinstance(cached_process_api.transform_api, CachedTransformService)
    # Because the cache is stored on the class itself this can be affect by
    # other tests, so save this off and take the difference to determin the result,
    # this is not great and hopefully we can find a better solution.
    start_ci = cached_process_api.transform_api._transform_template.cache_info()
    tf1 = process_api.transform_api.transform_template(sample_t)
    tf2 = process_api.transform_api.transform_template(sample_t)
    cached_tf1 = cached_process_api.transform_api.transform_template(sample_t)
    cached_tf2 = cached_process_api.transform_api.transform_template(sample_t)
    cached_tf3 = cached_process_api.transform_api.transform_template(sample_diff_t)
    # Check that the uncached and cached services are actually
    # returning non-identical results.
    assert tf1 is not cached_tf1
    assert tf1 is not cached_tf2
    assert tf1 is not cached_tf3
    # Check that the uncached service returns a brand new result everytime.
    assert tf1 is not tf2
    # Check that the cached service is returning the exact same, identical, result.
    assert cached_tf1 is cached_tf2
    # Even if the input templates are not identical (but are still equivalent).
    assert cached_tf1 is cached_tf3 and sample_t is not sample_diff_t
    # Check that the cached service and uncached services return
    # results that are equivalent (even though they are not (id)entical).
    assert struct_repr(tf1) == struct_repr(cached_tf1)
    assert struct_repr(tf2) == struct_repr(cached_tf1)
    # Now that we are setup we check that the cache is internally
    # working as we intended.
    ci = cached_process_api.transform_api._transform_template.cache_info()
    # cached_tf2 and cached_tf3 are hits after cached_tf1
    assert ci.hits - start_ci.hits == 2
    # cached_tf1 was a miss because cache was empty (brand new)
    assert ci.misses - start_ci.misses == 1
    cached_tf4 = cached_process_api.transform_api.transform_template(alt_t)
    # A different template produces a brand new tf.
    assert cached_tf1 is not cached_tf4
    # The template is new AND has a different structure so it also
    # produces an unequivalent tf.
    assert struct_repr(cached_tf1) != struct_repr(cached_tf4)
    """
'''


@pytest.mark.parametrize("to_html", PROCESSORS)
def test_repeat_calls(to_html):
    """Crude check for any unintended state being kept between calls."""

    def get_sample_t(idx, spread_attrs, button_text):
        return t"""<div><button data-key={idx} {spread_attrs}>{button_text}</button></div>"""

    for idx in range(3):
        spread_attrs = {"data-enabled": True}
        button_text = "PROCESS"
        sample_t = get_sample_t(idx, spread_attrs, button_text)
        assert (
            to_html(sample_t)
            == f'<div><button data-key="{idx}" data-enabled>PROCESS</button></div>'
        )


def get_select_t_with_list(options, selected_values):
    return t"""<select>{
        [
            t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>"
            for opt in options
        ]
    }</select>"""


def get_select_t_with_generator(options, selected_values):
    return t"""<select>{
        (
            t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>"
            for opt in options
        )
    }</select>"""


def get_select_t_with_concat(options, selected_values):
    parts = [t"<select>"]
    parts.extend(
        [
            t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>"
            for opt in options
        ]
    )
    parts.append(t"</select>")
    return sum(parts, t"")


@pytest.mark.parametrize("to_html", PROCESSORS)
@pytest.mark.parametrize(
    "provider",
    (
        get_select_t_with_list,
        get_select_t_with_generator,
        get_select_t_with_concat,
    ),
)
def test_process_template_iterables(to_html, provider):
    def get_color_select_t(selected_values: set, provider: t.Callable) -> Template:
        PRIMARY_COLORS = [("R", "Red"), ("Y", "Yellow"), ("B", "Blue")]
        assert set(selected_values).issubset(set([opt[0] for opt in PRIMARY_COLORS]))
        return provider(PRIMARY_COLORS, selected_values)

    no_selection_t = get_color_select_t(set(), provider)
    assert (
        to_html(no_selection_t)
        == '<select><option value="R">Red</option><option value="Y">Yellow</option><option value="B">Blue</option></select>'
    )
    selected_yellow_t = get_color_select_t({"Y"}, provider)
    assert (
        to_html(selected_yellow_t)
        == '<select><option value="R">Red</option><option value="Y" selected>Yellow</option><option value="B">Blue</option></select>'
    )


@pytest.mark.parametrize("to_html", PROCESSORS)
def test_component_integration(to_html):
    """Broadly test that common template component usage works."""

    def PageComponent(children, root_attrs=None):
        return t"""<div class="content" {root_attrs}>{children}</div>"""

    def FooterComponent(classes=("footer-default",)):
        return t'<div class="footer" class={classes}><a href="about">About</a></div>'

    def LayoutComponent(children, body_classes=None):
        return t"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body class={body_classes}>
    {children}
    <{FooterComponent} />
  </body>
</html>
"""

    content = "HTML never goes out of style."
    content_str = to_html(
        t"<{LayoutComponent} body_classes={['theme-default']}><{PageComponent}>{content}</{PageComponent}></{LayoutComponent}>"
    )
    assert (
        content_str
        == """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body class="theme-default">
    <div class="content">HTML never goes out of style.</div>
    <div class="footer footer-default"><a href="about">About</a></div>
  </body>
</html>
"""
    )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestInterpolatingHTMLInTemplateWithDynamicParentTag:
    """
    When a template does not have a parent tag we cannot determine the type
    of text that should be allowed and therefore we cannot determine how to
    escape that text.  Once the type is known we should escape any
    interpolations in that text correctly.
    """

    def test_dynamic_raw_text(self, to_html):
        """Type raw text should fail because template is already not allowed."""
        content = '<script>console.log("123!");</script>'
        content_t = t"{content}"
        with pytest.raises(
            ValueError, match="Recursive includes are not supported within script"
        ):
            content_t = t'<script>console.log("{123}!");</script>'
            _ = to_html(t"<script>{content_t}</script>")

    def test_dynamic_escapable_raw_text(self, to_html):
        """Type escapable raw text should fail because template is already not allowed."""
        content = '<script>console.log("123!");</script>'
        content_t = t"{content}"
        with pytest.raises(
            ValueError, match="Recursive includes are not supported within textarea"
        ):
            _ = to_html(t"<textarea>{content_t}</textarea>")

    def test_dynamic_normal_text(self, to_html):
        """Escaping should be applied when normal text type is goes into effect."""
        content = '<script>console.log("123!");</script>'
        content_t = t"{content}"
        LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
        assert (
            to_html(t"<div>{content_t}</div>")
            == f"<div>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</div>"
        )


@pytest.mark.parametrize("to_html", PROCESSORS)
class TestPagerComponentExample:
    @dataclass
    class Pager:
        left_pages: tuple = ()
        page: int = 0
        right_pages: tuple = ()
        prev_page: int | None = None
        next_page: int | None = None

    @dataclass
    class PagerDisplay:
        pager: TestPagerComponentExample.Pager
        paginate_url: Callable[[int], str]
        root_classes: tuple[str, ...] = ("cb", "tc", "w-100")
        part_classes: tuple[str, ...] = ("dib", "pa1")

        def __call__(self) -> Template:
            parts = [t"<div class={self.root_classes}>"]
            if self.pager.prev_page:
                parts.append(
                    t"<a class={self.part_classes} href={self.paginate_url(self.pager.prev_page)}>Prev</a>"
                )
            for left_page in self.pager.left_pages:
                parts.append(
                    t'<a class={self.part_classes} href="{self.paginate_url(left_page)}">{left_page}</a>'
                )
            parts.append(t"<span class={self.part_classes}>{self.pager.page}</span>")
            for right_page in self.pager.right_pages:
                parts.append(
                    t'<a class={self.part_classes} href="{self.paginate_url(right_page)}">{right_page}</a>'
                )
            if self.pager.next_page:
                parts.append(
                    t"<a class={self.part_classes} href={self.paginate_url(self.pager.next_page)}>Next</a>"
                )
            parts.append(t"</div>")
            return Template(*chain.from_iterable(parts))

    def test_example(self, to_html):
        def paginate_url(page: int) -> str:
            return f"/pages?page={page}"

        def Footer(pager, paginate_url, footer_classes=("footer",)) -> Template:
            return t"<div class={footer_classes}><{self.PagerDisplay} pager={pager} paginate_url={paginate_url} /></div>"

        pager = self.Pager(
            left_pages=(1, 2), page=3, right_pages=(4, 5), next_page=6, prev_page=None
        )
        content_t = t"<{Footer} pager={pager} paginate_url={paginate_url} />"
        res = to_html(content_t)
        print(res)
        assert (
            res
            == '<div class="footer"><div class="cb tc w-100"><a href="/pages?page=1" class="dib pa1">1</a><a href="/pages?page=2" class="dib pa1">2</a><span class="dib pa1">3</span><a href="/pages?page=4" class="dib pa1">4</a><a href="/pages?page=5" class="dib pa1">5</a><a href="/pages?page=6" class="dib pa1">Next</a></div></div>'
        )


@pytest.mark.skip(
    "SVG+MATHML: This needs ns context for case correcting tags and attributes."
)
@pytest.mark.parametrize("to_html", PROCESSORS)
def test_mathml(to_html):
    num = 1
    denom = 3
    mathml_t = t"""<p>
  The fraction
  <math>
    <mfrac>
      <mn>{num}</mn>
      <mn>{denom}</mn>
    </mfrac>
  </math>
  is not a decimal number.
</p>"""
    res = to_html(mathml_t)
    assert (
        str(res)
        == """<p>
  The fraction
  <math>
    <mfrac>
      <mn>1</mn>
      <mn>3</mn>
    </mfrac>
  </math>
  is not a decimal number.
</p>"""
    )


@pytest.mark.skip(
    "SVG+MATHML: This needs ns context for case correcting tags and attributes."
)
@pytest.mark.parametrize("to_html", PROCESSORS)
def test_svg(to_html):
    cx, cy, r, fill = 150, 100, 80, "green"
    svg_t = t"""<svg version="1.1" width="300" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="red" />
  <circle cx={cx} cy={cy} r={r} fill={fill} />
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    res = to_html(svg_t)
    assert (
        res
        == """<svg version="1.1" width="300" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="red"></rect>
  <circle cx="150" cy="100" r="80" fill="green"></circle>
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    )


@pytest.mark.skip("SVG+MATHML: This needs ns context for closing empty tags.")
@pytest.mark.parametrize("to_html", PROCESSORS)
def test_svg_self_closing_empty_elements(to_html):
    cx, cy, r, fill = 150, 100, 80, "green"
    svg_t = t"""<svg width="300" height="200">
  <rect width="100%" height="100%" fill="red" />
  <circle cx={cx} cy={cy} r={r} fill={fill} />
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    res = to_html(svg_t)
    assert (
        res
        == """<svg width="300" height="200">
  <rect width="100%" height="100%" fill="red" />
  <circle cx="150" cy="100" r="80" fill="green" />
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    )
