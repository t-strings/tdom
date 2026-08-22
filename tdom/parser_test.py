from string.templatelib import Interpolation, Template

import pytest

from .parser import TemplateParser, configure_source_tracker
from .placeholders import make_placeholder_config
from .template_utils import PartPosition, TemplateRef, TemplateSpan
from .tnodes import (
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TFragment,
    TInterpolatedAttribute,
    TLiteralAttribute,
    TNode,
    TSpreadAttribute,
    TTemplatedAttribute,
    TText,
)


def parse_root(t: Template) -> TNode:
    """Parse template to ttree and then return the root tnode."""
    return TemplateParser.parse(t).root


def literal_template_span(template: Template, text: str) -> TemplateSpan:
    """Return the span of a unique literal substring in a template."""
    matches = [
        (index, string.index(text))
        for index, string in enumerate(template.strings)
        if text in string
    ]
    assert len(matches) == 1
    string_index, offset = matches[0]
    return TemplateSpan(
        start=PartPosition(2 * string_index, offset),
        stop=PartPosition(2 * string_index, offset + len(text)),
    )


def test_parse_mixed_literal_content():
    node = parse_root(
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
    node = parse_root(t"")
    assert node == TFragment()


def test_parse_text():
    node = parse_root(t"Hello, world!")
    assert node == TText.literal("Hello, world!")


def test_parse_text_multiline():
    node = parse_root(t"""Hello, world!
  Hello, moon!
Hello, sun!
""")
    assert node == TText.literal("""Hello, world!
  Hello, moon!
Hello, sun!
""")


def test_parse_text_with_entities():
    node = parse_root(t"a &lt; b")
    assert node == TText.literal("a < b")


def test_parse_text_with_template_singleton():
    greeting = "Hello, World!"
    node = parse_root(t"{greeting}")
    assert node == TText(ref=TemplateRef(strings=("", "")))


def test_parse_text_with_template():
    who = "World"
    node = parse_root(t"Hello, {who}!")
    assert node == TText(ref=TemplateRef(strings=("Hello, ", "!")))


#
# Elements
#
def test_parse_void_element():
    node = parse_root(t"<br>")
    assert node == TElement("br")


def test_parse_void_element_self_closed():
    node = parse_root(t"<br />")
    assert node == TElement("br")


def test_parse_uppercase_void_element():
    node = parse_root(t"<BR>")
    assert node == TElement("br")


def test_parse_standard_element_with_text():
    node = parse_root(t"<div>Hello, world!</div>")
    assert node == TElement("div", children=(TText.literal("Hello, world!"),))


def test_parse_nested_elements():
    node = parse_root(t"<div><span>Nested</span> content</div>")
    assert node == TElement(
        "div",
        children=(
            TElement("span", children=(TText.literal("Nested"),)),
            TText.literal(" content"),
        ),
    )


def test_parse_element_with_template():
    who = "World"
    node = parse_root(t"<div>Hello, {who}!</div>")
    assert node == TElement(
        "div",
        children=(TText(ref=TemplateRef(strings=("Hello, ", "!"))),),
    )


def test_parse_element_with_template_singleton():
    greeting = "Hello, World!"
    node = parse_root(t"<div>{greeting}</div>")
    assert node == TElement("div", children=(TText(ref=TemplateRef(strings=("", ""))),))


def test_parse_multiple_voids():
    node = parse_root(t"<br><hr><hr /><hr /><br /><br><br>")
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
    node = parse_root(t"<p>&lt;/p&gt;</p>")
    assert node == TElement(
        "p",
        children=(TText.literal("</p>"),),
    )


def test_parse_script_tag_content():
    node = parse_root(t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>")
    assert node == TElement(
        "script",
        children=(TText.literal("if (a < b && c > d) { alert('wow'); }"),),
    )


def test_parse_script_with_entities():
    # The <script> tag (and <style>) tag uses the CDATA content model.
    node = parse_root(t"<script>var x = 'a &amp; b';</script>")
    assert node == TElement(
        "script",
        children=(TText.literal("var x = 'a &amp; b';"),),
    ), "Entities SHOULD NOT be evaluated in scripts."


def test_parse_textarea_tag_content():
    node = parse_root(t"<textarea>if (a < b && c > d) {{ alert('wow'); }}</textarea>")
    assert node == TElement(
        "textarea",
        children=(TText.literal("if (a < b && c > d) { alert('wow'); }"),),
    )


def test_parse_textarea_with_entities():
    # The <textarea> (and <title>) tag uses the RCDATA content model.
    node = parse_root(t"<textarea>var x = 'a &amp; b';</textarea>")
    assert node == TElement(
        "textarea",
        children=(TText.literal("var x = 'a & b';"),),
    ), "Entities SHOULD be evaluated in textarea/title."


def test_parse_title_unusual():
    node = parse_root(t"<title>My & Awesome <Site></title>")
    assert node == TElement(
        "title",
        children=(TText.literal("My & Awesome <Site>"),),
    )


def test_parse_mismatched_tags():
    with pytest.raises(ValueError):
        _ = parse_root(t"<div><span>Mismatched</div></span>")


def test_parse_unclosed_tag():
    with pytest.raises(ValueError):
        _ = parse_root(t"<div>Unclosed")


def test_parse_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_root(t"Unopened</div>")


def test_self_closing_tags():
    node = parse_root(t"<div/><p></p>")
    assert node == TFragment(
        children=(
            TElement("div"),
            TElement("p"),
        )
    )


def test_nested_self_closing_tags():
    node = parse_root(t"<div><br><div /><br></div>")
    assert node == TElement(
        "div", children=(TElement("br"), TElement("div"), TElement("br"))
    )
    node = parse_root(t"<div><div /></div>")
    assert node == TElement("div", children=(TElement("div"),))


def test_self_closing_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_root(t"<div /></div>")


def test_self_closing_void_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_root(t"<input /></input>")


#
# Attributes
#
def test_literal_attrs():
    node = parse_root(
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
    node = parse_root(t'<a title="&lt;">Link</a>')
    assert node == TElement(
        "a",
        attrs=(TLiteralAttribute("title", "<"),),
        children=(TText.literal("Link"),),
    )


def test_literal_attr_order():
    node = parse_root(t'<a title="a" href="b" title="c"></a>')
    assert isinstance(node, TElement)
    assert node.attrs == (
        TLiteralAttribute("title", "a"),
        TLiteralAttribute("href", "b"),
        TLiteralAttribute("title", "c"),  # dupe IS allowed
    )


def test_interpolated_attr():
    value1 = 42
    value2 = 99
    node = parse_root(t'<div value1="{value1}" value2={value2} />')
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
    node = parse_root(t'<div value1="{value1}-burrito" value2="neato-{value2}-wow" />')
    value1_ref = TemplateRef(strings=("", "-burrito"))
    value2_ref = TemplateRef(strings=("neato-", "-wow"), i_start=1)
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
    node = parse_root(t"<div {spread_attrs} />")
    assert node == TElement(
        "div",
        attrs=(TSpreadAttribute(i_index=0),),
        children=(),
    )


def test_templated_attribute_name_error():
    with pytest.raises(ValueError):
        attr_name = "some-attr"
        _ = parse_root(t'<div {attr_name}="value" />')


def test_templated_attribute_name_and_value_error():
    with pytest.raises(ValueError):
        attr_name = "some-attr"
        value = "value"
        _ = parse_root(t'<div {attr_name}="{value}" />')


def test_adjacent_spread_attrs_error():
    with pytest.raises(ValueError):
        attrs1 = {}
        attrs2 = {}
        _ = parse_root(t"<div {attrs1}{attrs2} />")


#
# Comments
#
def test_parse_comment():
    node = parse_root(t"<!-- This is a comment -->")
    assert node == TComment.literal(" This is a comment ")


def test_parse_comment_interpolation():
    text = "comment"
    node = parse_root(t"<!-- This is a {text} -->")
    assert node == TComment(ref=TemplateRef(strings=(" This is a ", " ")))


#
# Doctypes
#
def test_parse_doctype():
    node = parse_root(t"<!DOCTYPE html>")
    assert node == TDocumentType("html")


def test_parse_doctype_interpolation_error():
    extra = "SYSTEM"
    with pytest.raises(ValueError):
        _ = parse_root(t"<!DOCTYPE html {extra}>")


def test_unsupported_decl_error():
    with pytest.raises(NotImplementedError):
        _ = parse_root(t"<!doctype-alt html500>")  # Unknown declaration
    with pytest.raises(NotImplementedError):
        _ = parse_root(t"<!doctype>")  # missing DTD


#
# Components.
#
def test_component_element_with_children():
    def Component(children):
        return t"{children}"

    template = t"<{Component}><div>Hello, World!</div></{Component}>"
    node = parse_root(template)
    assert node == TComponent(
        start_i_index=0,
        end_i_index=1,
        children_span=literal_template_span(template, "<div>Hello, World!</div>"),
    )


def test_component_element_self_closing():
    def Component():
        pass

    node = parse_root(t"<{Component} />")
    assert node == TComponent(start_i_index=0)


def test_component_element_with_closing_tag():
    def Component():
        pass

    node = parse_root(t"<{Component}></{Component}>")
    assert node == TComponent(
        start_i_index=0,
        end_i_index=1,
        children_span=TemplateSpan(PartPosition(2, 1), PartPosition(2, 1)),
    )


def test_component_element_special_case_mismatched_closing_tag_still_parses():
    def Component1():
        pass

    def Component2():
        pass

    node = parse_root(t"<{Component1}></{Component2}>")
    assert node == TComponent(
        start_i_index=0,
        end_i_index=1,
        children_span=TemplateSpan(PartPosition(2, 1), PartPosition(2, 1)),
    )


def test_component_element_invalid_closing_tag():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = parse_root(t"<{Component}></div>")


def test_component_element_invalid_opening_tag():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = parse_root(t"<div></{Component}>")


def test_adjacent_start_component_tag_error():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = parse_root(t"<{Component}{Component}></{Component}>")


def test_adjacent_end_component_tag_error():
    def Component():
        pass

    with pytest.raises(ValueError):
        _ = parse_root(t"<{Component}></{Component}{Component}>")


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
    tnode = parse_root(template)
    value_ref = TemplateRef(strings=(config.prefix, config.suffix))
    assert tnode == TElement(
        "div",
        attrs=(TTemplatedAttribute(name="data-tricky", value_ref=value_ref),),
    )


def test_unresolved_placeholder():
    t = t"<div>{0}<span>{1}</span>{2}</div>"
    tp = TemplateParser()
    tp.feed_template(t)
    # This would be a bug in the parser so we have to fabricate
    # this error manually.
    tp.get_source().placeholders.add_placeholder(3)
    with pytest.raises(ValueError, match="Some placeholders were never resolved"):
        tp.close()


class TestSourceTracker:
    @pytest.mark.parametrize("t", (t"", t"simple"))
    def test_only_string(self, t: Template):
        st = configure_source_tracker(t)
        itr = iter(st)
        part = next(itr)
        assert isinstance(part, str) and part == t.strings[0]
        assert itr.index == 0
        with pytest.raises(StopIteration):
            _ = next(itr)
        assert itr.index == 0, "Still at 0."

    def test_iter(self):
        t = t"<div>{0}</div>"
        st = configure_source_tracker(t)
        itr = iter(st)
        parts = []
        parts.append(next(itr))
        assert itr.index == 0
        assert not itr.has_placeholders()
        assert parts[0] == t.strings[0], "String parts pass through."
        parts.append(next(itr))
        assert itr.index == 1
        assert itr.has_placeholders(), "Placeholder was addeded."
        tref_find = st.find_placeholders(parts[1])
        assert itr.has_placeholders() and tref_find.i_start == 0
        tref_removed = st.remove_placeholders(parts[1])
        assert not itr.has_placeholders() and tref_removed.i_start == 0, (
            "Placeholder removed."
        )
        parts.append(next(itr))
        assert itr.index == 2
        with pytest.raises(StopIteration):
            next(itr)
        assert itr.index == 2, (
            "Once the iter is exhausted the index remains at the last element."
        )


class TestIncompleteParsing:
    def test_dangling_quotes(self):
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = parse_root(t"<div a='")
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = parse_root(t'<div a="')

    def test_unfinished_attribute(self):
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = parse_root(t"<div a=")

    def test_placeholder_missing_from_dangling_quote(self):
        with pytest.raises(ValueError, match="Parser expects more data"):
            _ = parse_root(t'<div a="{None}')


class TestComponentChildrenSpan:
    @pytest.fixture
    def Component(self):
        def Component(children: Template, **attrs: str) -> Template:
            return t""

        return Component

    def test_extract_no_content(self, Component):
        node = parse_root(t"<{Component}></{Component}>")
        assert node == TComponent(
            start_i_index=0,
            end_i_index=1,
            children_span=TemplateSpan(PartPosition(2, 1), PartPosition(2, 1)),
        )

    def test_extract_startend(self, Component):
        node = parse_root(t"<{Component} />")
        assert node == TComponent(
            start_i_index=0,
            end_i_index=None,
            children_span=None,
        )

    def test_extract(self, Component):
        template = t"<{Component}><div>Hello, World!</div></{Component}>"
        node = parse_root(template)
        assert node == TComponent(
            start_i_index=0,
            end_i_index=1,
            children_span=literal_template_span(template, "<div>Hello, World!</div>"),
        )

    def test_extract_with_attr_interpolation(self, Component):
        # Unquoted ...
        template = t"<{Component} title={'Skip over this.'}><div>Hello, World!</div></{Component}>"
        node = parse_root(template)
        assert node == TComponent(
            start_i_index=0,
            end_i_index=2,
            attrs=(TInterpolatedAttribute(name="title", value_i_index=1),),
            children_span=literal_template_span(template, "<div>Hello, World!</div>"),
        )
        # Quoted...
        node2 = parse_root(
            t'<{Component} title="{"Skip over this."}"><div>Hello, World!</div></{Component}>'
        )
        assert isinstance(node2, TComponent)
        assert node2.attrs == (TInterpolatedAttribute(name="title", value_i_index=1),)
        assert node2.children_span is not None

    def test_extract_with_literal_attr_gt_char(self, Component):
        template = t'<{Component} title="1 > 0"><div>Hello, World!</div></{Component}>'
        node = parse_root(template)
        assert node == TComponent(
            start_i_index=0,
            end_i_index=1,
            attrs=(TLiteralAttribute("title", "1 > 0"),),
            children_span=literal_template_span(template, "<div>Hello, World!</div>"),
        )

    def test_extract_with_interpolated_attr_literal_attr_gt_char(self, Component):
        template = t'<{Component} id={"simple"} title="1 > 0"><div>Hello, World!</div></{Component}>'
        node = parse_root(template)
        assert node == TComponent(
            start_i_index=0,
            end_i_index=2,
            attrs=(
                TInterpolatedAttribute(name="id", value_i_index=1),
                TLiteralAttribute("title", "1 > 0"),
            ),
            children_span=literal_template_span(template, "<div>Hello, World!</div>"),
        )

    def test_extract_with_templated_attr_gt_char(self, Component):
        template = t'<{Component} id="{"header"}_{"container"}" title="1 > 0"><div>Hello, World!</div></{Component}>'
        node = parse_root(template)
        assert node == TComponent(
            start_i_index=0,
            end_i_index=3,
            attrs=(
                TTemplatedAttribute(
                    "id", TemplateRef(strings=("", "_", ""), i_start=1)
                ),
                TLiteralAttribute("title", "1 > 0"),
            ),
            children_span=literal_template_span(template, "<div>Hello, World!</div>"),
        )

    def test_extract_with_interpolated_children_after_attribute(self, Component):
        child = "child"
        template = (
            t"<{Component} title={'attribute'}>before {child} after</{Component}>"
        )

        node = parse_root(template)

        assert isinstance(node, TComponent)
        assert node.children_span is not None
        children = node.children_span.extract(template)
        assert children.strings == ("before ", " after")
        assert children.values == (child,)


class TestSourcePos:
    """
    Test that common nodes have a source position translated and set during parsing.
    """

    @pytest.mark.parametrize(
        ("t", "part_pos"),
        (
            (t"ABC<div></div>", PartPosition(0, offset=len("ABC"))),
            (t"{' '}<div></div>", PartPosition(2, offset=0)),
        ),
    )
    def test_el(self, t: Template, part_pos: PartPosition):
        root = parse_root(t)
        assert isinstance(root, TFragment)
        node = root.children[1]
        assert isinstance(node, TElement) and node.source_pos == part_pos

    @pytest.mark.parametrize(
        ("t", "part_pos"),
        (
            (t"<div></div>ABC", PartPosition(0, offset=len("<div></div>"))),
            (t"<div>{' '}</div>ABC", PartPosition(2, offset=len("</div>"))),
        ),
    )
    def test_text(self, t: Template, part_pos: PartPosition):
        root = parse_root(t)
        assert isinstance(root, TFragment)
        node = root.children[1]
        assert isinstance(node, TText) and node.source_pos == part_pos

    @pytest.mark.parametrize(
        ("t", "part_pos"),
        (
            (t"  <!doctype html>", PartPosition(0, offset=2)),
            (t"{' '}<!doctype html>", PartPosition(2, 0)),
        ),
    )
    def test_doctype(self, t: Template, part_pos: PartPosition):
        root = parse_root(t)
        assert isinstance(root, TFragment)
        node = root.children[1]
        assert isinstance(node, TDocumentType) and node.source_pos == part_pos

    @pytest.mark.parametrize(
        ("t", "part_pos"),
        (
            (t"  <!--comment-->", PartPosition(0, offset=2)),
            (t"<div>{'ABC'}</div><!--comment-->", PartPosition(2, len("</div>"))),
        ),
    )
    def test_comment(self, t: Template, part_pos: PartPosition):
        root = parse_root(t)
        assert isinstance(root, TFragment)
        node = root.children[1]
        assert isinstance(node, TComment) and node.source_pos == part_pos

    def test_component(self):
        def Comp() -> Template:
            return t""

        for t, part_pos in (
            (t"  <{Comp} />", PartPosition(0, offset=len("  "))),
            (t"  {'ABC'}DEF<{Comp} />", PartPosition(2, offset=len("DEF"))),
        ):
            root = parse_root(t)
            assert isinstance(root, TFragment)
            node = root.children[1]
            assert isinstance(node, TComponent) and node.source_pos == part_pos


class TestSourceInfo:
    """
    Test that elements and components have correct entries in the sinfo_table after parsing.
    """

    def test_el(self):
        ttree = TemplateParser.parse(t"<div></div>")
        sinfo_table = ttree.unpack_sinfo_table()
        node = ttree.root
        assert (
            isinstance(node, TElement)
            and sinfo_table
            and node.source_pos is not None
            and node.source_pos in sinfo_table
        )
        sinfo = sinfo_table[node.source_pos]
        assert sinfo.startend == False
        assert sinfo.starttag_pos == PartPosition(
            0, 0
        ) and sinfo.endtag_pos == PartPosition(0, len("<div>"))
        assert sinfo.starttag_span == TemplateSpan(
            PartPosition(0, 0), PartPosition(0, len("<div>"))
        )

    def test_el_self_closed(self):
        ttree = TemplateParser.parse(t"<div />")
        sinfo_table = ttree.unpack_sinfo_table()
        node = ttree.root
        assert (
            isinstance(node, TElement)
            and sinfo_table
            and node.source_pos is not None
            and node.source_pos in sinfo_table
        )
        sinfo = sinfo_table[node.source_pos]
        assert sinfo.startend == True
        assert sinfo.starttag_pos == PartPosition(0, 0) and sinfo.endtag_pos is None
        assert sinfo.starttag_span == TemplateSpan(
            PartPosition(0, 0), PartPosition(0, len("<div />"))
        )

    def test_component(self):
        def Comp() -> Template:
            return t""

        ttree = TemplateParser.parse(t"<{Comp}></{Comp}>")
        sinfo_table = ttree.unpack_sinfo_table()
        node = ttree.root
        assert (
            isinstance(node, TComponent)
            and sinfo_table
            and node.source_pos is not None
            and node.source_pos in sinfo_table
        )
        sinfo = sinfo_table[node.source_pos]
        assert sinfo.startend == False
        assert sinfo.starttag_pos == PartPosition(
            0, 0
        ) and sinfo.endtag_pos == PartPosition(2, len(">"))
        assert sinfo.starttag_span == TemplateSpan(
            PartPosition(0, 0), PartPosition(2, len(">"))
        )

    def test_component_self_closed(self):
        def Comp() -> Template:
            return t""

        ttree = TemplateParser.parse(t"<{Comp} />")
        sinfo_table = ttree.unpack_sinfo_table()
        node = ttree.root
        assert (
            isinstance(node, TComponent)
            and sinfo_table
            and node.source_pos is not None
            and node.source_pos in sinfo_table
        )
        sinfo = sinfo_table[node.source_pos]
        assert sinfo.startend == True
        assert sinfo.starttag_pos == PartPosition(0, 0) and sinfo.endtag_pos is None
        assert sinfo.starttag_span == TemplateSpan(
            PartPosition(0, 0), PartPosition(2, len(" />"))
        )

    def test_multiline_component_spans(self):
        def Component(children):
            return children

        template = t'<{Component}\n title="literal"\n>child</{Component}>'
        ttree = TemplateParser.parse(template)
        node = ttree.root
        assert isinstance(node, TComponent)
        assert node.children_span is not None
        assert node.source_pos is not None

        sinfo = ttree.unpack_sinfo_table()[node.source_pos]
        extracted_starttag = sinfo.starttag_span.extract(template)
        extracted_children = node.children_span.extract(template)

        assert extracted_starttag.strings == ("<", '\n title="literal"\n>')
        assert extracted_starttag.values == (Component,)
        assert extracted_children.strings == ("child",)

    def test_empty_sinfo_table(self):
        ttree = TemplateParser.parse(t"<!doctype html>ABC")
        sinfo_table = ttree.unpack_sinfo_table()
        assert not sinfo_table
