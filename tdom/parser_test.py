import pytest
from string.templatelib import Template, Interpolation
from functools import lru_cache

from .nodes import (
    TNode,
    TComment,
    TDocumentType,
    TElement,
    TFragment,
    TText,
    TComponent,
    InterpolatedAttribute,
    TemplatedAttribute,
    StaticAttribute,
    SpreadAttribute,
)
from .parser import _parse_html, parse_html, CachedTemplate


class TestHelpers:
    """
    Helpers to create what we think the template nodes and their properties
    should look like after they were parsed out from a Template().
    """

    def to_basic_template(self, *parts):
        """Shorthand to convert str() to strings and int() to interpolations and then unpack into Template()."""
        return Template(
            *(
                [
                    part if isinstance(part, str) else Interpolation(part, "", None, "")
                    for part in parts
                ]
            )
        )

    def text(self, *parts, format_spec=""):
        return TText(self.to_basic_template(*parts))

    def comment(self, *parts, format_spec=""):
        return TComment(self.to_basic_template(*parts))

    def el(self, tag, attrs=(), children=()):
        return TElement(tag, attrs, children)

    def comp(
        self,
        starttag_interpolation_index,
        endtag_interpolation_index,
        starttag_string_index,
        endtag_string_index,
        attrs=(),
        children=(),
    ):
        return TComponent(
            starttag_interpolation_index=starttag_interpolation_index,
            endtag_interpolation_index=endtag_interpolation_index,
            starttag_string_index=starttag_string_index,
            endtag_string_index=endtag_string_index,
            attrs=attrs,
            children=children,
        )

    def interpolated_attr(self, k: str, values_index: int):
        """An interpolated attribute, ie. `alt={alt}`."""
        return InterpolatedAttribute(k, values_index)

    def templated_attr(self, k: str, *template_parts: str | int):
        """A templated attribute, ie. `alt="A picture of {alt}`."""
        return TemplatedAttribute(k, self.to_basic_template(*template_parts))

    def spread_attr(self, values_index: int):
        """A spread attribute, ie. `<div {attrs}>`."""
        return SpreadAttribute(values_index)

    def static_attr(self, k: str, v: str | None):
        """A regular attribute with a value: `alt="The ocean"`, or bare: `checked`."""
        return StaticAttribute(k, v)


th = TestHelpers()


def test_parse_empty():
    node = parse_html(t"")
    assert node == TFragment()


def test_parse_text_simple():
    node = parse_html(t"Hello, world!")
    assert node == th.text("Hello, world!")


def test_parse_text_with_entities():
    node = parse_html(t"Panini&apos;s")
    assert node == th.text("Panini's")


def test_parse_void_element():
    node = parse_html(t"<br>")
    assert node == th.el("br")


def test_parse_void_element_self_closed():
    node = parse_html(t"<br />")
    assert node == th.el("br")


def test_parse_uppercase_void_element():
    node = parse_html(t"<BR>")
    assert node == th.el("br")


def test_parse_standard_element_with_text():
    node = parse_html(t"<div>Hello, world!</div>")
    assert node == th.el("div", children=tuple([th.text("Hello, world!")]))


def test_parse_nested_elements():
    node = parse_html(t"<div><span>Nested</span> content</div>")
    assert node == th.el(
        "div",
        children=tuple(
            [
                th.el("span", children=tuple([th.text("Nested")])),
                th.text(" content"),
            ]
        ),
    )


def test_parse_element_with_attributes():
    node = parse_html(t'<a href="https://example.com" target="_blank">Link</a>')
    assert node == th.el(
        "a",
        attrs=(
            th.static_attr("href", "https://example.com"),
            th.static_attr("target", "_blank"),
        ),
        children=tuple([th.text("Link")]),
    )


def test_parse_element_attribute_order():
    node = parse_html(t'<a title="a" href="b" title="c"></a>')
    assert node == TElement(
        "a",
        attrs=(
            th.static_attr("title", "a"),
            th.static_attr("href", "b"),
            th.static_attr("title", "c"),
        ),
        children=(),
    )


def test_parse_comment():
    node = parse_html(t"<!-- This is a comment -->")
    assert node == th.comment(" This is a comment ")


def test_parse_doctype():
    node = parse_html(t"<!DOCTYPE html>")
    assert node == TDocumentType("html")


def test_parse_explicit_fragment_empty():
    node = parse_html(t"<></>")
    assert node == TFragment(children=())


def test_parse_explicit_fragment_with_content():
    node = parse_html(t"<><div>Item 1</div><div>Item 2</div></>")
    assert node == TFragment(
        children=tuple(
            [
                th.el("div", children=tuple([th.text("Item 1")])),
                th.el("div", children=tuple([th.text("Item 2")])),
            ]
        )
    )


def test_parse_explicit_fragment_with_text():
    node = parse_html(t"<>Hello, <span>world</span>!</>")
    assert node == TFragment(
        children=tuple(
            [
                th.text("Hello, "),
                th.el("span", children=tuple([th.text("world")])),
                th.text("!"),
            ]
        )
    )


def test_parse_explicit_fragment_nested():
    node = parse_html(t"<div><>Nested <span>fragment</span></></div>")
    assert node == th.el(
        "div",
        children=tuple(
            [
                TFragment(
                    children=tuple(
                        [
                            th.text("Nested "),
                            th.el("span", children=tuple([th.text("fragment")])),
                        ]
                    )
                )
            ]
        ),
    )


def test_parse_multiple_voids():
    node = parse_html(t"<br><hr><hr /><hr /><br /><br><br>")
    assert node == TFragment(
        children=tuple(
            [
                th.el("br"),
                th.el("hr"),
                th.el("hr"),
                th.el("hr"),
                th.el("br"),
                th.el("br"),
                th.el("br"),
            ]
        )
    )


def test_parse_mixed_content():
    node = parse_html(
        t'<!DOCTYPE html><!-- Comment --><div class="container">'
        t"Hello, <br class='funky' />world <!-- neato -->!</div>"
    )
    assert node == TFragment(
        children=tuple(
            [
                TDocumentType("html"),
                th.comment(" Comment "),
                th.el(
                    "div",
                    attrs=(th.static_attr("class", "container"),),
                    children=tuple(
                        [
                            th.text("Hello, "),
                            th.el("br", attrs=(th.static_attr("class", "funky"),)),
                            th.text("world "),
                            th.comment(" neato "),
                            th.text("!"),
                        ]
                    ),
                ),
            ]
        )
    )


def test_parse_entities_are_unescaped():
    node = parse_html(t"<p>&lt;/p&gt;</p>")
    assert node == th.el(
        "p",
        children=tuple([th.text("</p>")]),
    )


def test_parse_script_tag_content():
    node = parse_html(t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>")
    assert node == th.el(
        "script", children=tuple([th.text("if (a < b && c > d) { alert('wow'); }")])
    )


def test_parse_script_with_entities():
    # The <script> tag (and <style>) tag uses the CDATA content model.
    node = parse_html(t"<script>var x = 'a &amp; b';</script>")
    assert node == th.el("script", children=tuple([th.text("var x = 'a &amp; b';")]))


def test_parse_textarea_tag_content():
    node = parse_html(t"<textarea>if (a < b && c > d) {{ alert('wow'); }}</textarea>")
    assert node == th.el(
        "textarea", children=tuple([th.text("if (a < b && c > d) { alert('wow'); }")])
    )


def test_parse_textarea_with_entities():
    # The <textarea> (and <title>) tag uses the RCDATA content model.
    node = parse_html(t"<textarea>var x = 'a &amp; b';</textarea>")
    assert node == th.el(
        "textarea",
        children=tuple([th.text("var x = 'a & b';")]),
    )


def test_parse_title_unusual():
    node = parse_html(t"<title>My & Awesome <Site></title>")
    assert node == th.el(
        "title",
        children=tuple([th.text("My & Awesome <Site>")]),
    )


def test_parse_mismatched_tags():
    with pytest.raises(ValueError):
        _ = parse_html(t"<div><span>Mismatched</div></span>")


def test_parse_unclosed_tag():
    with pytest.raises(ValueError):
        _ = parse_html(t"<div>Unclosed")


def test_parse_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_html(t"Unopened</div>")


def test_self_closing_tags():
    node = parse_html(t"<div/><p></p>")
    assert node == TFragment(
        children=tuple(
            [
                th.el("div"),
                th.el("p"),
            ]
        )
    )


def test_nested_self_closing_tags():
    node = parse_html(t"<div><br><div /><br></div>")
    assert node == TElement(
        "div", children=tuple([TElement("br"), TElement("div"), TElement("br")])
    )
    node = parse_html(t"<div><div /></div>")
    assert node == TElement("div", children=tuple([TElement("div")]))


def test_self_closing_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_html(t"<div /></div>")


def test_self_closing_void_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_html(t"<input /></input>")


def test_parse_dynamic_attr():
    src = "example"
    node = parse_html(t"<a href={src}></a>")
    assert node == th.el("a", attrs=(th.interpolated_attr("href", 0),))


def test_parse_dynamic_attr_spread():
    attrs = dict(src="example")
    node = parse_html(t"<a {attrs}></a>")
    assert isinstance(node, TElement) and node == th.el("a", attrs=(th.spread_attr(0),))


def test_parse_dynamic_attr_template():
    src = "example"
    node = parse_html(t'<a href="/{src}"></a>')
    assert node == th.el("a", attrs=(th.templated_attr("href", "/", 0),))


def test_parse_attrs_mixed():
    src = "example"
    attrs = {"target": "_blank"}
    blurb = "This example is great!"
    node = parse_html(
        t'<a title="A great example." href="/{src}" attributionsrc={True} {attrs}>Check this out! {blurb}</a>'
    )
    assert node == th.el(
        "a",
        attrs=(
            th.static_attr("title", "A great example."),
            th.templated_attr("href", "/", 0),
            th.interpolated_attr("attributionsrc", 1),
            th.spread_attr(2),
        ),
        children=tuple([th.text("Check this out! ", 3)]),
    )


def test_parse_component_basic():
    def DivWrapper(attrs, embedded_t):
        return t"<div>{embedded_t}</div>"

    node = parse_html(t"<body><{DivWrapper}></{DivWrapper}></body>")
    assert node == th.el(
        "body",
        children=tuple([th.comp(0, 1, starttag_string_index=1, endtag_string_index=2)]),
    )


def test_parse_component_xhtml_close():
    def DivWrapper(attrs, embedded_t):
        return t"<div>{embedded_t}</div>"

    node = parse_html(t"<body><{DivWrapper} /></body>")
    assert node == th.el(
        "body",
        children=tuple([th.comp(0, 0, starttag_string_index=1, endtag_string_index=1)]),
    )


def test_parse_component_attrs():
    def DivWrapper(attrs, embedded_t):
        wrap_t = t"<div style={attrs.get('style', None) or None}>{embedded_t}</div>"
        if attrs.get("doubletime"):
            wrap_t = t"<div>{wrap_t}</div>"
        return wrap_t

    title = "Wrap it up"
    config = {"doubletime": True}
    node = parse_html(
        t'<body><{DivWrapper} style="background-color: red" title={title} {config}></{DivWrapper}></body>'
    )
    assert node == th.el(
        "body",
        children=tuple(
            [
                th.comp(
                    0,
                    3,
                    attrs=(
                        th.static_attr("style", "background-color: red"),
                        th.interpolated_attr("title", 1),
                        th.spread_attr(2),
                    ),
                    starttag_string_index=3,
                    endtag_string_index=4,
                ),
            ]
        ),
    )


@pytest.fixture()
def parse_html_simulation():
    """
    Simulate parse_html/_parse_html using the lru_cache.
    """

    @lru_cache(maxsize=512)
    def _simulated_parse_html(cached_template: CachedTemplate) -> TNode:
        return _parse_html.__wrapped__(cached_template)

    def simulated_parse_html(template: Template) -> TNode:
        return _simulated_parse_html(CachedTemplate(template))

    yield simulated_parse_html, _simulated_parse_html
    _simulated_parse_html.cache_clear()


def hits_misses_helper(caching_func):
    """Shorthand for unpacking a cached func's cache info over-and-over."""

    def _hits_misses():
        info = caching_func.cache_info()
        return (info.hits, info.misses)

    return _hits_misses


def test_parse_html_cache_hit_after_first_parse(parse_html_simulation):
    simulated_parse_html, _simulated_parse_html = parse_html_simulation
    hits_misses = hits_misses_helper(_simulated_parse_html)
    assert hits_misses() == (0, 0)

    in_template = t"<div>Parsing {'html'}!</div>"
    out_tnode = th.el("div", children=tuple([th.text("Parsing ", 0, "!")]))

    assert simulated_parse_html(in_template) == out_tnode
    assert hits_misses() == (0, 1)  # MISS!
    assert simulated_parse_html(in_template) == out_tnode
    assert hits_misses() == (1, 1)  # HIT!


def test_parse_html_cache_hit_same_strings(parse_html_simulation):
    simulated_parse_html, _simulated_parse_html = parse_html_simulation
    hits_misses = hits_misses_helper(_simulated_parse_html)
    assert hits_misses() == (0, 0)

    in_template = t"<div>Parsing {'html'}!</div>"
    alt_template = t"<div>Parsing {100}!</div>"
    out_tnode = th.el("div", children=tuple([th.text("Parsing ", 0, "!")]))

    # Strings equal but interpolation values are different
    assert (
        alt_template.strings == in_template.strings
        and alt_template.values != in_template.values
    )

    assert simulated_parse_html(in_template) == out_tnode
    assert hits_misses() == (0, 1)  # MISS!
    assert simulated_parse_html(in_template) == out_tnode
    assert hits_misses() == (1, 1)  # HIT!
    assert simulated_parse_html(alt_template) == out_tnode
    assert hits_misses() == (2, 1)  # HIT!


def test_cached_template_eq():
    ct1 = CachedTemplate(t"<div>Parsing {'html'}!</div>")
    ct2 = CachedTemplate(t"<div>Parsing {100}!</div>")
    assert (
        ct1.template.strings == ct2.template.strings
        and ct1.template.values != ct2.template.values
    )
    assert ct1 == ct2 and ct1 == ct1

    ct3 = CachedTemplate(t"<div>Still parsing {'html'}!</div>")
    assert (
        ct1.template.strings != ct3.template.strings
        and ct1.template.values == ct3.template.values
    )
    assert ct1 != ct3


def test_cached_template_hash():
    ct1 = CachedTemplate(t"<div>Parsing {'html'}!</div>")
    ct2 = CachedTemplate(t"<div>Parsing {100}!</div>")
    assert (
        ct1.template.strings == ct2.template.strings
        and ct1.template.values != ct2.template.values
    )
    assert hash(ct1) == hash(ct2)

    ct3 = CachedTemplate(t"<div>Still parsing {'html'}!</div>")
    assert (
        ct1.template.strings != ct3.template.strings
        and ct1.template.values == ct3.template.values
    )
    assert hash(ct1) != hash(ct3)
