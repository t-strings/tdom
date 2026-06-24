from string.templatelib import Interpolation, Template

import pytest

from .parser import TemplateParser
from .placeholders import make_placeholder_config
from .source import FrozenPosition
from .template_utils import TemplateRef
from .tnodes import (
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TFragment,
    TInterpolatedAttribute,
    TLiteralAttribute,
    TSpreadAttribute,
    TTemplatedAttribute,
    TText,
)


def test_parse_mixed_literal_content():
    node = TemplateParser.parse(
        t"<!DOCTYPE html>"
        t"<!-- Comment -->"
        t'<div class="container">'
        t"Hello, <br class='funky' />world <!-- neato -->!"
        t"</div>"
    )
    assert node == TFragment(
        children=(
            TDocumentType("html"),
            TComment.literal(" Comment "),
            TElement(
                "div",
                attrs=(TLiteralAttribute("class", "container"),),
                children=(
                    TText.literal("Hello, "),
                    TElement("br", attrs=(TLiteralAttribute("class", "funky"),)),
                    TText.literal("world "),
                    TComment.literal(" neato "),
                    TText.literal("!"),
                ),
            ),
        )
    )


#
# Text
#
def test_parse_empty():
    node = TemplateParser.parse(t"")
    assert node == TFragment()


def test_parse_text():
    node = TemplateParser.parse(t"Hello, world!")
    assert node == TText.literal("Hello, world!")


def test_parse_text_multiline():
    node = TemplateParser.parse(t"""Hello, world!
  Hello, moon!
Hello, sun!
""")
    assert node == TText.literal("""Hello, world!
  Hello, moon!
Hello, sun!
""")


def test_parse_text_with_entities():
    node = TemplateParser.parse(t"a &lt; b")
    assert node == TText.literal("a < b")


def test_parse_text_with_template_singleton():
    greeting = "Hello, World!"
    node = TemplateParser.parse(t"{greeting}")
    assert node == TText(ref=TemplateRef(strings=("", ""), i_indexes=(0,)))


def test_parse_text_with_template():
    who = "World"
    node = TemplateParser.parse(t"Hello, {who}!")
    assert node == TText(ref=TemplateRef(strings=("Hello, ", "!"), i_indexes=(0,)))


#
# Elements
#
def test_parse_void_element():
    node = TemplateParser.parse(t"<br>")
    assert node == TElement("br")


def test_parse_void_element_self_closed():
    node = TemplateParser.parse(t"<br />")
    assert node == TElement("br")


def test_parse_uppercase_void_element():
    node = TemplateParser.parse(t"<BR>")
    assert node == TElement("br")


def test_parse_standard_element_with_text():
    node = TemplateParser.parse(t"<div>Hello, world!</div>")
    assert node == TElement("div", children=(TText.literal("Hello, world!"),))


def test_parse_nested_elements():
    node = TemplateParser.parse(t"<div><span>Nested</span> content</div>")
    assert node == TElement(
        "div",
        children=(
            TElement("span", children=(TText.literal("Nested"),)),
            TText.literal(" content"),
        ),
    )


def test_parse_element_with_template():
    who = "World"
    node = TemplateParser.parse(t"<div>Hello, {who}!</div>")
    assert node == TElement(
        "div",
        children=(TText(ref=TemplateRef(strings=("Hello, ", "!"), i_indexes=(0,))),),
    )


def test_parse_element_with_template_singleton():
    greeting = "Hello, World!"
    node = TemplateParser.parse(t"<div>{greeting}</div>")
    assert node == TElement(
        "div", children=(TText(ref=TemplateRef(strings=("", ""), i_indexes=(0,))),)
    )


def test_parse_multiple_voids():
    node = TemplateParser.parse(t"<br><hr><hr /><hr /><br /><br><br>")
    assert node == TFragment(
        children=(
            TElement("br"),
            TElement("hr"),
            TElement("hr"),
            TElement("hr"),
            TElement("br"),
            TElement("br"),
            TElement("br"),
        )
    )


def test_parse_text_entities():
    node = TemplateParser.parse(t"<p>&lt;/p&gt;</p>")
    assert node == TElement(
        "p",
        children=(TText.literal("</p>"),),
    )


def test_parse_script_tag_content():
    node = TemplateParser.parse(
        t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>"
    )
    assert node == TElement(
        "script",
        children=(TText.literal("if (a < b && c > d) { alert('wow'); }"),),
    )


def test_parse_script_with_entities():
    # The <script> tag (and <style>) tag uses the CDATA content model.
    node = TemplateParser.parse(t"<script>var x = 'a &amp; b';</script>")
    assert node == TElement(
        "script",
        children=(TText.literal("var x = 'a &amp; b';"),),
    ), "Entities SHOULD NOT be evaluated in scripts."


def test_parse_textarea_tag_content():
    node = TemplateParser.parse(
        t"<textarea>if (a < b && c > d) {{ alert('wow'); }}</textarea>"
    )
    assert node == TElement(
        "textarea",
        children=(TText.literal("if (a < b && c > d) { alert('wow'); }"),),
    )


def test_parse_textarea_with_entities():
    # The <textarea> (and <title>) tag uses the RCDATA content model.
    node = TemplateParser.parse(t"<textarea>var x = 'a &amp; b';</textarea>")
    assert node == TElement(
        "textarea",
        children=(TText.literal("var x = 'a & b';"),),
    ), "Entities SHOULD be evaluated in textarea/title."


def test_parse_title_unusual():
    node = TemplateParser.parse(t"<title>My & Awesome <Site></title>")
    assert node == TElement(
        "title",
        children=(TText.literal("My & Awesome <Site>"),),
    )


def test_parse_mismatched_tags():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div><span>Mismatched</div></span>")


def test_parse_unclosed_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div>Unclosed")


def test_parse_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"Unopened</div>")


def test_self_closing_tags():
    node = TemplateParser.parse(t"<div/><p></p>")
    assert node == TFragment(
        children=(
            TElement("div"),
            TElement("p"),
        )
    )


def test_nested_self_closing_tags():
    node = TemplateParser.parse(t"<div><br><div /><br></div>")
    assert node == TElement(
        "div", children=(TElement("br"), TElement("div"), TElement("br"))
    )
    node = TemplateParser.parse(t"<div><div /></div>")
    assert node == TElement("div", children=(TElement("div"),))


def test_self_closing_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div /></div>")


def test_self_closing_void_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<input /></input>")


#
# Attributes
#
def test_literal_attrs():
    node = TemplateParser.parse(
        t"<a"
        t" id=example_link"  # no quotes allowed without spaces
        t" autofocus"  # bare / boolean
        t' title=""'  # empty attribute
        t' href="https://example.com" target="_blank"'
        t">Link</a>"
    )
    assert node == TElement(
        "a",
        attrs=(
            TLiteralAttribute("id", "example_link"),
            TLiteralAttribute("autofocus", None),
            TLiteralAttribute("title", ""),
            TLiteralAttribute("href", "https://example.com"),
            TLiteralAttribute("target", "_blank"),
        ),
        children=(TText.literal("Link"),),
    )


def test_literal_attr_entities():
    node = TemplateParser.parse(t'<a title="&lt;">Link</a>')
    assert node == TElement(
        "a",
        attrs=(TLiteralAttribute("title", "<"),),
        children=(TText.literal("Link"),),
    )


def test_literal_attr_order():
    node = TemplateParser.parse(t'<a title="a" href="b" title="c"></a>')
    assert isinstance(node, TElement)
    assert node.attrs == (
        TLiteralAttribute("title", "a"),
        TLiteralAttribute("href", "b"),
        TLiteralAttribute("title", "c"),  # dupe IS allowed
    )


def test_interpolated_attr():
    value1 = 42
    value2 = 99
    node = TemplateParser.parse(t'<div value1="{value1}" value2={value2} />')
    assert node == TElement(
        "div",
        attrs=(
            TInterpolatedAttribute("value1", 0),
            TInterpolatedAttribute("value2", 1),
        ),
        children=(),
    )


def test_templated_attr():
    value1 = 42
    value2 = 99
    node = TemplateParser.parse(
        t'<div value1="{value1}-burrito" value2="neato-{value2}-wow" />'
    )
    value1_ref = TemplateRef(strings=("", "-burrito"), i_indexes=(0,))
    value2_ref = TemplateRef(strings=("neato-", "-wow"), i_indexes=(1,))
    assert node == TElement(
        "div",
        attrs=(
            TTemplatedAttribute("value1", value1_ref),
            TTemplatedAttribute("value2", value2_ref),
        ),
        children=(),
    )


def test_spread_attr():
    spread_attrs = {}
    node = TemplateParser.parse(t"<div {spread_attrs} />")
    assert node == TElement(
        "div",
        attrs=(TSpreadAttribute(i_index=0),),
        children=(),
    )


def test_templated_attribute_name_error():
    with pytest.raises(ValueError):
        attr_name = "some-attr"
        _ = TemplateParser.parse(t'<div {attr_name}="value" />')


def test_templated_attribute_name_and_value_error():
    with pytest.raises(ValueError):
        attr_name = "some-attr"
        value = "value"
        _ = TemplateParser.parse(t'<div {attr_name}="{value}" />')


def test_adjacent_spread_attrs_error():
    with pytest.raises(ValueError):
        attrs1 = {}
        attrs2 = {}
        _ = TemplateParser.parse(t"<div {attrs1}{attrs2} />")


#
# Comments
#
def test_parse_comment():
    node = TemplateParser.parse(t"<!-- This is a comment -->")
    assert node == TComment.literal(" This is a comment ")


def test_parse_comment_interpolation():
    text = "comment"
    node = TemplateParser.parse(t"<!-- This is a {text} -->")
    assert node == TComment(
        ref=TemplateRef(strings=(" This is a ", " "), i_indexes=(0,))
    )


#
# Doctypes
#
def test_parse_doctype():
    node = TemplateParser.parse(t"<!DOCTYPE html>")
    assert node == TDocumentType("html")


def test_parse_doctype_interpolation_error():
    extra = "SYSTEM"
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<!DOCTYPE html {extra}>")


def test_unsupported_decl_error():
    with pytest.raises(NotImplementedError):
        _ = TemplateParser.parse(t"<!doctype-alt html500>")  # Unknown declaration
    with pytest.raises(NotImplementedError):
        _ = TemplateParser.parse(t"<!doctype>")  # missing DTD


#
# Components.
#
def test_component_element_with_children():
    def Component(children):
        return t"{children}"

    node = TemplateParser.parse(t"<{Component}><div>Hello, World!</div></{Component}>")
    assert node == TComponent(
        start_i_index=0,
        end_i_index=1,
        children_ref=TemplateRef(strings=("<div>Hello, World!</div>",), i_indexes=()),
    )


def test_component_element_self_closing():
    def Component():
        pass

    node = TemplateParser.parse(t"<{Component} />")
    assert node == TComponent(start_i_index=0)


def test_component_element_with_closing_tag():
    def Component():
        pass

    node = TemplateParser.parse(t"<{Component}></{Component}>")
    assert node == TComponent(start_i_index=0, end_i_index=1)


def test_component_element_special_case_mismatched_closing_tag_still_parses():
    def Component1():
        pass

    def Component2():
        pass

    node = TemplateParser.parse(t"<{Component1}></{Component2}>")
    assert node == TComponent(start_i_index=0, end_i_index=1)


def test_component_element_invalid_closing_tag():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<{Component}></div>")


def test_component_element_invalid_opening_tag():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div></{Component}>")


def test_adjacent_start_component_tag_error():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<{Component}{Component}></{Component}>")


def test_adjacent_end_component_tag_error():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<{Component}></{Component}{Component}>")


def test_unmatched_end_component_tag_error():
    def Component():
        pass

    with pytest.raises(ValueError, match="Unexpected closing component tag"):
        _ = TemplateParser.parse(t"</{Component}>")


def test_placeholder_collision_avoidance():
    config = make_placeholder_config()
    # This test is to ensure that our placeholder detection avoids collisions
    # even with content that might look like a placeholder.
    tricky = "0"
    template = Template(
        f'<div data-tricky="{config.prefix}',
        Interpolation(tricky, "tricky", None, ""),
        f'{config.suffix}"></div>',
    )
    tnode = TemplateParser.parse(template)
    value_ref = TemplateRef(strings=(config.prefix, config.suffix), i_indexes=(0,))
    assert tnode == TElement(
        "div", attrs=(TTemplatedAttribute(name="data-tricky", value_ref=value_ref),)
    )


class TestIncompleteParsing:
    def test_dangling_quotes(self):
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = TemplateParser.parse(t"<div a='")
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = TemplateParser.parse(t'<div a="')

    def test_unfinished_attribute(self):
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = TemplateParser.parse(t"<div a=")

    def test_placeholder_missing_from_dangling_quote(self):
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = TemplateParser.parse(t'<div a="{None}')


class TestComponentExtractChildrenTemplate:
    @pytest.fixture
    def Component(self):
        def Component(children: Template, **attrs: str) -> Template:
            return t""

        return Component

    def test_extract_no_content(self, Component):
        node = TemplateParser.parse(t"<{Component}></{Component}>")
        assert node == TComponent(
            start_i_index=0,
            end_i_index=1,
            children_ref=TemplateRef(strings=("",), i_indexes=()),
        )

    def test_extract_startend(self, Component):
        node = TemplateParser.parse(t"<{Component} />")
        assert node == TComponent(
            start_i_index=0,
            end_i_index=None,
            children_ref=TemplateRef(strings=("",), i_indexes=()),
        )

    def test_extract(self, Component):
        node = TemplateParser.parse(
            t"<{Component}><div>Hello, World!</div></{Component}>"
        )
        assert node == TComponent(
            start_i_index=0,
            end_i_index=1,
            children_ref=TemplateRef(
                strings=("<div>Hello, World!</div>",), i_indexes=()
            ),
        )

    def test_extract_with_attr_interpolation(self, Component):
        # Unquoted ...
        node = TemplateParser.parse(
            t"<{Component} title={'Skip over this.'}><div>Hello, World!</div></{Component}>"
        )
        assert node == TComponent(
            start_i_index=0,
            end_i_index=2,
            attrs=(TInterpolatedAttribute(name="title", value_i_index=1),),
            children_ref=TemplateRef(
                strings=("<div>Hello, World!</div>",), i_indexes=()
            ),
        )
        # Quoted...
        node2 = TemplateParser.parse(
            t'<{Component} title="{"Skip over this."}"><div>Hello, World!</div></{Component}>'
        )
        assert node2 == node

    def test_extract_with_literal_attr_gt_char(self, Component):
        node = TemplateParser.parse(
            t'<{Component} title="1 > 0"><div>Hello, World!</div></{Component}>'
        )
        assert node == TComponent(
            start_i_index=0,
            end_i_index=1,
            attrs=(TLiteralAttribute("title", "1 > 0"),),
            children_ref=TemplateRef(
                strings=("<div>Hello, World!</div>",), i_indexes=()
            ),
        )

    def test_extract_with_interpolated_attr_literal_attr_gt_char(self, Component):
        node = TemplateParser.parse(
            t'<{Component} id={"simple"} title="1 > 0"><div>Hello, World!</div></{Component}>'
        )
        assert node == TComponent(
            start_i_index=0,
            end_i_index=2,
            attrs=(
                TInterpolatedAttribute(name="id", value_i_index=1),
                TLiteralAttribute("title", "1 > 0"),
            ),
            children_ref=TemplateRef(
                strings=("<div>Hello, World!</div>",), i_indexes=()
            ),
        )

    def test_extract_with_templated_attr_gt_char(self, Component):
        node = TemplateParser.parse(
            t'<{Component} id="{"header"}_{"container"}" title="1 > 0"><div>Hello, World!</div></{Component}>'
        )
        assert node == TComponent(
            start_i_index=0,
            end_i_index=3,
            attrs=(
                TTemplatedAttribute(
                    "id", TemplateRef(strings=("", "_", ""), i_indexes=(1, 2))
                ),
                TLiteralAttribute("title", "1 > 0"),
            ),
            children_ref=TemplateRef(
                strings=("<div>Hello, World!</div>",), i_indexes=()
            ),
        )


class TestComponentUnquotedAttrValueWithAmbiguousSlash:
    @pytest.fixture
    def comp_maker(self):
        def maker(suffix=None):
            def _Comp(children: Template, title: str) -> Template:
                return children

            if suffix is not None:
                _Comp.__name__ = f"{_Comp.__name__}__{suffix}"
            return _Comp

        return maker

    @pytest.fixture
    def Comp(self):
        def _Comp(children: Template, title: str) -> Template:
            return children

        return _Comp

    @pytest.fixture
    def Comp2(self):
        def _Comp2(children: Template, title: str) -> Template:
            return children

        return _Comp2

    def test_comp_unquoted_attr_value_error_root(self, Comp):
        with pytest.raises(
            ValueError, match="Did you mean to quote the last attribute"
        ):
            _ = TemplateParser.parse(t"<{Comp} title=today/>")

    def test_comp_unquoted_attr_value_error_nested_in_el(self, Comp):
        with pytest.raises(
            ValueError, match="Did you mean to quote the last attribute"
        ):
            _ = TemplateParser.parse(t"<div><{Comp} title=today/></div>")

    def test_comp_unquoted_attr_value_error_single_nested_in_comp(self, Comp, Comp2):
        with pytest.raises(
            ValueError, match="Did you mean to quote the last attribute"
        ):
            _ = TemplateParser.parse(t"<{Comp2}><{Comp} title=today/></{Comp2}>")

    def test_comp_unquoted_attr_value_error_double_nested_in_comp(self, comp_maker):
        Comp1, Comp2, Comp3 = comp_maker("1"), comp_maker("2"), comp_maker("3")
        with pytest.raises(
            ValueError, match="Did you mean to quote the last attribute"
        ):
            _ = TemplateParser.parse(
                t"<{Comp2}><{Comp1}><{Comp3} title=today/></{Comp1}></{Comp2}>"
            )


def PositionComp() -> Template:
    return t""


@pytest.mark.parametrize(
    "chunk",
    (
        (TElement, t"<span></span>"),
        (TComment, t"<!--ok-->"),
        (TDocumentType, t"<!doctype html>"),
        (TComponent, t"<{PositionComp}></{PositionComp}>"),
        (TText, t"Just a simple text."),
    ),
)
def test_tnode_parser_position(chunk):
    tnode = TemplateParser.parse(t"<div>" + chunk[1] + t"</div>")
    assert tnode.tag == "div" and len(tnode.children) == 1
    el = tnode.children[0]
    assert isinstance(el, chunk[0])
    assert el.parser_pos == FrozenPosition(line=1, offset=len("<div>"))
