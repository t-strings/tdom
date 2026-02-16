import datetime
import typing as t
from dataclasses import dataclass
from string.templatelib import Interpolation, Template
from itertools import product

import pytest
from markupsafe import Markup

from .placeholders import make_placeholder_config
from .processor import to_html, prep_component_kwargs
from .callables import get_callable_info
from .escaping import escape_html_text

# --------------------------------------------------------------------------
# Basic HTML parsing tests
# --------------------------------------------------------------------------


#
# Text
#
def test_empty():
    assert to_html(t"") == ""


def test_text_literal():
    assert to_html(t"Hello, world!") == "Hello, world!"


def test_text_singleton():
    greeting = "Hello, Alice!"
    assert to_html(t"{greeting}", last_parent_tag="div") == "Hello, Alice!"
    assert to_html(t"{greeting}", last_parent_tag="script") == "Hello, Alice!"
    assert to_html(t"{greeting}", last_parent_tag="style") == "Hello, Alice!"
    assert to_html(t"{greeting}", last_parent_tag="textarea") == "Hello, Alice!"
    assert to_html(t"{greeting}", last_parent_tag="title") == "Hello, Alice!"


def test_text_singleton_without_parent():
    greeting = "</script>"
    with pytest.raises(NotImplementedError):
        _ = to_html(t"{greeting}", last_parent_tag=None)


def test_text_singleton_explicit_parent_script():
    greeting = "</script>"
    res = to_html(t"{greeting}", last_parent_tag="script")
    assert res == "\\x3c/script>"
    assert res != "</script>"


def test_text_singleton_explicit_parent_div():
    greeting = "</div>"
    res = to_html(t"{greeting}", last_parent_tag="div")
    assert res == "&lt;/div&gt;"
    assert res != "</div>"


def test_text_template():
    name = "Alice"
    assert to_html(t"Hello, {name}!", last_parent_tag="div") == "Hello, Alice!"


def test_text_template_escaping():
    name = "Alice & Bob"
    assert (
        to_html(t"Hello, {name}!", last_parent_tag="div") == "Hello, Alice &amp; Bob!"
    )


#
# Comments.
#
def test_comment():
    assert to_html(t"<!--This is a comment-->") == "<!--This is a comment-->"


def test_comment_template():
    text = "comment"
    assert to_html(t"<!--This is a {text}-->") == "<!--This is a comment-->"


def test_comment_template_escaping():
    text = "-->comment"
    assert to_html(t"<!--This is a {text}-->") == "<!--This is a --&gt;comment-->"


#
# Document types.
#
def test_parse_document_type():
    assert to_html(t"<!doctype html>") == "<!DOCTYPE html>"


#
# Elements
#
def test_parse_void_element():
    assert to_html(t"<br>") == "<br />"


def test_parse_void_element_self_closed():
    assert to_html(t"<br />") == "<br />"


def test_parse_chain_of_void_elements():
    # Make sure our handling of CPython issue #69445 is reasonable.
    assert (
        to_html(t"<br><hr><img src='image.png' /><br /><hr>")
        == '<br /><hr /><img src="image.png" /><br /><hr />'
    )


def test_parse_element_with_text():
    assert to_html(t"<p>Hello, world!</p>") == "<p>Hello, world!</p>"


def test_parse_nested_elements():
    assert (
        to_html(t"<div><p>Hello</p><p>World</p></div>")
        == "<div><p>Hello</p><p>World</p></div>"
    )


def test_parse_entities_are_escaped():
    res = to_html(t"<p>&lt;/p&gt;</p>")
    assert res == "<p>&lt;/p&gt;</p>", res


def test_parse_entities_are_escaped_no_parent_tag():
    res = to_html(t"&lt;/p&gt;")
    assert res == "&lt;/p&gt;", "Default to standard escaping."


"""
def test_parse_entities_are_escaped_parent_tag_div():
    res = to_html(t"<?tdom div>&lt;/p&gt;", last_parent_tag='div')
    assert res == "&lt;/p&gt;", res
"""

# --------------------------------------------------------------------------
# Interpolated text content
# --------------------------------------------------------------------------


def test_interpolated_text_content():
    name = "Alice"
    assert to_html(t"<p>Hello, {name}!</p>") == "<p>Hello, Alice!</p>"


def test_escaping_of_interpolated_text_content():
    name = "<Alice & Bob>"
    assert to_html(t"<p>Hello, {name}!</p>") == "<p>Hello, &lt;Alice &amp; Bob&gt;!</p>"


class Convertible:
    def __str__(self):
        return "string"

    def __repr__(self):
        return "repr"


def test_conversions():
    c = Convertible()
    assert f"{c!s}" == "string"
    assert f"{c!r}" == "repr"
    assert to_html(t"<div>{c!s}</div>") == "<div>string</div>"
    assert to_html(t"<div>{c!r}</div>") == "<div>repr</div>"
    assert (
        to_html(t"<div>{'😊'!a}</div>") == f"<div>{escape_html_text(ascii('😊'))}</div>"
    )


def test_interpolated_in_content_node():
    # https://github.com/t-strings/tdom/issues/68
    evil = "</style><script>alert('whoops');</script><style>"
    LT = "&lt;"
    assert (
        to_html(t"<style>{evil}{evil}</style>")
        == f"<style>{LT}/style><script>alert('whoops');</script><style>{LT}/style><script>alert('whoops');</script><style></style>"
    )


def test_interpolated_trusted_in_content_node():
    # https://github.com/t-strings/tdom/issues/68
    assert (
        to_html(t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>")
        == "<script>if (a < b && c > d) { alert('wow'); }</script>"
    )


def test_script_elements_error():
    nested_template = t"<div></div>"
    # Putting non-text content inside a script is not allowed.
    with pytest.raises(ValueError):
        _ = to_html(t"<script>{nested_template}</script>")


# --------------------------------------------------------------------------
# Interpolated non-text content
# --------------------------------------------------------------------------


def test_interpolated_false_content():
    assert to_html(t"<div>{False}</div>") == "<div>False</div>"


def test_interpolated_none_content():
    assert to_html(t"<div>{None}</div>") == "<div></div>"


def test_interpolated_zero_arg_function():
    def get_value():
        return "dynamic"

    assert (
        to_html(t"<p>The value is {get_value:callback}.</p>")
        == "<p>The value is dynamic.</p>"
    )


def test_interpolated_multi_arg_function_fails():
    def add(a, b):  # pragma: no cover
        return a + b

    with pytest.raises(TypeError):
        _ = to_html(t"<p>The sum is {add:callback}.</p>")


# --------------------------------------------------------------------------
# Raw HTML injection tests
# --------------------------------------------------------------------------


def test_raw_html_injection_with_markupsafe():
    raw_content = Markup("<strong>I am bold</strong>")
    assert (
        to_html(t"<div>{raw_content}</div>") == "<div><strong>I am bold</strong></div>"
    )


def test_raw_html_injection_with_dunder_html_protocol():
    class SafeContent:
        def __init__(self, text):
            self._text = text

        def __html__(self):
            # In a real app, this would come from a sanitizer or trusted source
            return f"<em>{self._text}</em>"

    content = SafeContent("emphasized")
    assert (
        to_html(t"<p>Here is some {content:safe}.</p>")
        == "<p>Here is some <em>emphasized</em>.</p>"
    )


def test_raw_html_injection_with_format_spec():
    raw_content = "<u>underlined</u>"
    assert (
        to_html(t"<p>This is {raw_content:safe} text.</p>")
        == "<p>This is <u>underlined</u> text.</p>"
    )


def test_raw_html_injection_with_markupsafe_unsafe_format_spec():
    supposedly_safe = Markup("<i>italic</i>")
    assert (
        to_html(t"<p>This is {supposedly_safe:unsafe} text.</p>")
        == "<p>This is &lt;i&gt;italic&lt;/i&gt; text.</p>"
    )


# --------------------------------------------------------------------------
# Conditional rendering and control flow
# --------------------------------------------------------------------------


def test_conditional_rendering_with_if_else():
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


@pytest.mark.skip(
    "This is another design situation where we try to do everything and it complicates the API. If we take False then we probably take True which also does what False does?"
)
def test_conditional_rendering_with_and():
    show_warning = True
    warning_message = t'<div class="warning">Warning!</div>'
    assert (
        to_html(t"<main>{show_warning and warning_message}</main>")
        == '<main><div class="warning">Warning!</div></main>'
    )

    show_warning = False
    assert (
        to_html(t"<main>{show_warning and warning_message}</main>") == "<main></main>"
    )


# --------------------------------------------------------------------------
# Interpolated nesting of templates and elements
# --------------------------------------------------------------------------


def test_interpolated_template_content():
    child = t"<span>Child</span>"
    assert to_html(t"<div>{child}</div>") == "<div><span>Child</span></div>"


@pytest.mark.skip("Allow node injection?")
def test_interpolated_element_content():
    # child = Element("span", children=[Text("Child")])
    # assert to_html(t"<div>{child}</div>") == "<div><span>Child</span></div>"
    pass


def test_interpolated_nonstring_content():
    number = 42
    assert to_html(t"<p>The answer is {number}.</p>") == "<p>The answer is 42.</p>"


def test_list_items():
    items = ["Apple", "Banana", "Cherry"]
    assert (
        to_html(t"<ul>{[t'<li>{item}</li>' for item in items]}</ul>")
        == "<ul><li>Apple</li><li>Banana</li><li>Cherry</li></ul>"
    )


def test_nested_list_items():
    # TODO XXX this is a pretty abusrd test case; clean it up when refactoring
    outer = ["fruit", "more fruit"]
    inner = ["apple", "banana", "cherry"]
    inner_items = [t"<li>{item}</li>" for item in inner]
    outer_items = [t"<li>{category}<ul>{inner_items}</ul></li>" for category in outer]
    assert (
        to_html(t"<ul>{outer_items}</ul>")
        == "<ul><li>fruit<ul><li>apple</li><li>banana</li><li>cherry</li></ul></li><li>more fruit<ul><li>apple</li><li>banana</li><li>cherry</li></ul></li></ul>"
    )


# --------------------------------------------------------------------------
# Attributes
# --------------------------------------------------------------------------


def test_literal_attrs():
    assert (
        to_html(
            (
                t"<a "
                t" id=example_link"  # no quotes allowed without spaces
                t" autofocus"  # bare / boolean
                t' title=""'  # empty attribute
                t' href="https://example.com" target="_blank"'
                t"></a>"
            )
        )
        == '<a id="example_link" autofocus title="" href="https://example.com" target="_blank"></a>'
    )


def test_literal_attr_escaped():
    assert to_html(t'<a title="&lt;"></a>') == '<a title="&lt;"></a>'


def test_interpolated_attr():
    url = "https://example.com/"
    assert to_html(t'<a href="{url}"></a>') == '<a href="https://example.com/"></a>'


def test_interpolated_attr_escaped():
    url = 'https://example.com/?q="test"&lang=en'
    assert (
        to_html(t'<a href="{url}"></a>')
        == '<a href="https://example.com/?q=&#34;test&#34;&amp;lang=en"></a>'
    )


def test_interpolated_attr_unquoted():
    id = "roquefort"
    assert to_html(t"<div id={id}></div>") == '<div id="roquefort"></div>'


def test_interpolated_attr_true():
    disabled = True
    assert (
        to_html(t"<button disabled={disabled}></button>")
        == "<button disabled></button>"
    )


def test_interpolated_attr_false():
    disabled = False
    assert to_html(t"<button disabled={disabled}></button>") == "<button></button>"


def test_interpolated_attr_none():
    disabled = None
    assert to_html(t"<button disabled={disabled}></button>") == "<button></button>"


def test_interpolate_attr_empty_string():
    assert to_html(t'<div title=""></div>') == '<div title=""></div>'


def test_spread_attr():
    attrs = {"href": "https://example.com/", "target": "_blank"}
    assert (
        to_html(t"<a {attrs}></a>")
        == '<a href="https://example.com/" target="_blank"></a>'
    )


def test_spread_attr_none():
    attrs = None
    assert to_html(t"<a {attrs}></a>") == "<a></a>"


def test_spread_attr_type_errors():
    for attrs in (0, [], (), False, True):
        with pytest.raises(TypeError):
            _ = to_html(t"<a {attrs}></a>")


def test_templated_attr_mixed_interpolations_start_end_and_nest():
    left, middle, right = 1, 3, 5
    prefix, suffix = t'<div data-range="', t'"></div>'
    # Check interpolations at start, middle and/or end of templated attr
    # or a combination of those to make sure text is not getting dropped.
    for left_part, middle_part, right_part in product(
        (t"{left}", Template(str(left))),
        (t"{middle}", Template(str(middle))),
        (t"{right}", Template(str(right))),
    ):
        test_t = prefix + left_part + t"-" + middle_part + t"-" + right_part + suffix
        assert to_html(test_t) == '<div data-range="1-3-5"></div>'


def test_templated_attr_no_quotes():
    start = 1
    end = 5
    assert (
        to_html(t"<div data-range={start}-{end}></div>")
        == '<div data-range="1-5"></div>'
    )


def test_attr_merge_disjoint_interpolated_attr_spread_attr():
    attrs = {"href": "https://example.com/", "id": "link1"}
    target = "_blank"
    assert (
        to_html(t"<a {attrs} target={target}></a>")
        == '<a href="https://example.com/" id="link1" target="_blank"></a>'
    )


def test_attr_merge_overlapping_spread_attrs():
    attrs1 = {"href": "https://example.com/", "id": "overwrtten"}
    attrs2 = {"target": "_blank", "id": "link1"}
    assert (
        to_html(t"<a {attrs1} {attrs2}></a>")
        == '<a href="https://example.com/" target="_blank" id="link1"></a>'
    )


def test_attr_merge_replace_literal_attr_str_str():
    assert (
        to_html(t'<div title="default" {dict(title="fresh")}></div>')
        == '<div title="fresh"></div>'
    )


def test_attr_merge_replace_literal_attr_str_true():
    assert (
        to_html(t'<div title="default" {dict(title=True)}></div>')
        == "<div title></div>"
    )


def test_attr_merge_replace_literal_attr_true_str():
    assert (
        to_html(t"<div title {dict(title='fresh')}></div>")
        == '<div title="fresh"></div>'
    )


def test_attr_merge_remove_literal_attr_str_none():
    assert to_html(t'<div title="default" {dict(title=None)}></div>') == "<div></div>"


def test_attr_merge_remove_literal_attr_true_none():
    assert to_html(t"<div title {dict(title=None)}></div>") == "<div></div>"


def test_attr_merge_other_literal_attr_intact():
    assert (
        to_html(t'<img title="default" {dict(alt="fresh")}>')
        == '<img title="default" alt="fresh" />'
    )


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
    assert (
        to_html(template)
        == f'<div data-tricky="{config.prefix}{tricky}{config.suffix}"></div>'
    )


#
# Special data attribute handling.
#
def test_interpolated_data_attributes():
    data = {"user-id": 123, "role": "admin", "wild": True, "false": False, "none": None}
    assert (
        to_html(t"<div data={data}>User Info</div>")
        == '<div data-user-id="123" data-role="admin" data-wild>User Info</div>'
    )


def test_data_attr_toggle_to_str():
    for res in [
        to_html(t"<div data-selected data={dict(selected='yes')}></div>"),
        to_html(t'<div data-selected="no" data={dict(selected="yes")}></div>'),
    ]:
        assert res == '<div data-selected="yes"></div>'


def test_data_attr_toggle_to_true():
    res = to_html(t'<div data-selected="yes" data={dict(selected=True)}></div>')
    assert res == "<div data-selected></div>"


def test_data_attr_unrelated_unaffected():
    res = to_html(t"<div data-selected data={dict(active=True)}></div>")
    assert res == "<div data-selected data-active></div>"


def test_data_attr_templated_error():
    data1 = {"user-id": "user-123"}
    data2 = {"role": "admin"}
    with pytest.raises(TypeError):
        _ = to_html(t'<div data="{data1} {data2}"></div>')


def test_data_attr_none():
    button_data = None
    res = to_html(t"<button data={button_data}>X</button>")
    assert res == "<button>X</button>"


def test_data_attr_errors():
    for v in [False, [], (), 0, "data?"]:
        with pytest.raises(TypeError):
            _ = to_html(t"<button data={v}>X</button>")


def test_data_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    res = to_html(t'<p data="passthru" id={"resolved"}></p>')
    assert res == '<p data="passthru" id="resolved"></p>', (
        "A single literal attribute should not trigger data expansion."
    )


#
# Special aria attribute handling.
#
def test_aria_templated_attr_error():
    aria1 = {"label": "close"}
    aria2 = {"hidden": "true"}
    with pytest.raises(TypeError):
        _ = to_html(t'<div aria="{aria1} {aria2}"></div>')


def test_aria_interpolated_attr_dict():
    aria = {"label": "Close", "hidden": True, "another": False, "more": None}
    res = to_html(t"<button aria={aria}>X</button>")
    assert (
        res
        == '<button aria-label="Close" aria-hidden="true" aria-another="false">X</button>'
    )


def test_aria_interpolate_attr_none():
    button_aria = None
    res = to_html(t"<button aria={button_aria}>X</button>")
    assert res == "<button>X</button>"


def test_aria_attr_errors():
    for v in [False, [], (), 0, "aria?"]:
        with pytest.raises(TypeError):
            _ = to_html(t"<button aria={v}>X</button>")


def test_aria_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    res = to_html(t'<p aria="passthru" id={"resolved"}></p>')
    assert res == '<p aria="passthru" id="resolved"></p>', (
        "A single literal attribute should not trigger aria expansion."
    )


#
# Special class attribute handling.
#
def test_interpolated_class_attribute():
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


def test_interpolated_class_attribute_with_multiple_placeholders():
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


def test_interpolated_attribute_spread_with_class_attribute():
    attrs = {"id": "button1", "class": ["btn", "btn-primary"]}
    res = to_html(t"<button {attrs}>Click me</button>")
    assert res == '<button id="button1" class="btn btn-primary">Click me</button>'


def test_class_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    res = to_html(t'<p class="red red" id={"veryred"}></p>')
    assert res == '<p class="red red" id="veryred"></p>', (
        "A single literal attribute should not trigger class accumulator."
    )


def test_class_none_ignored():
    class_item = None
    res = to_html(t"<p class={class_item}></p>")
    assert res == "<p></p>"
    # Also ignored inside a sequence.
    res = to_html(t"<p class={[class_item]}></p>")
    assert res == "<p></p>"


def test_class_type_errors():
    for class_item in (False, True, 0):
        with pytest.raises(TypeError):
            _ = to_html(t"<p class={class_item}></p>")
        with pytest.raises(TypeError):
            _ = to_html(t"<p class={[class_item]}></p>")


def test_class_merge_literals():
    res = to_html(t'<p class="red" class="blue"></p>')
    assert res == '<p class="red blue"></p>'


def test_class_merge_literal_then_interpolation():
    class_item = "blue"
    res = to_html(t'<p class="red" class="{[class_item]}"></p>')
    assert res == '<p class="red blue"></p>'


#
# Special style attribute handling.
#
def test_style_literal_attr_passthru():
    p_id = "para1"  # non-literal attribute to cause attr resolution
    res = to_html(t'<p style="color: red" id={p_id}>Warning!</p>')
    assert res == '<p style="color: red" id="para1">Warning!</p>'


def test_style_in_interpolated_attr():
    styles = {"color": "red", "font-weight": "bold", "font-size": "16px"}
    res = to_html(t"<p style={styles}>Warning!</p>")
    assert (
        res == '<p style="color: red; font-weight: bold; font-size: 16px">Warning!</p>'
    )


def test_style_in_templated_attr():
    color = "red"
    res = to_html(t'<p style="color: {color}">Warning!</p>')
    assert res == '<p style="color: red">Warning!</p>'


def test_style_in_spread_attr():
    attrs = {"style": {"color": "red"}}
    res = to_html(t"<p {attrs}>Warning!</p>")
    assert res == '<p style="color: red">Warning!</p>'


def test_style_merged_from_all_attrs():
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


def test_style_override_left_to_right():
    suffix = t"></p>"
    parts = [
        (t'<p style="color: red"', "color: red"),
        (t" style={dict(color='blue')}", "color: blue"),
        (t''' style="color: {"green"}"''', "color: green"),
        (t""" {dict(style=dict(color="yellow"))}""", "color: yellow"),
    ]
    for index in range(len(parts)):
        expected_style = parts[index][1]
        t = sum([part[0] for part in parts[: index + 1]], t"") + suffix
        res = to_html(t)
        assert res == f'<p style="{expected_style}"></p>'


def test_interpolated_style_attribute_multiple_placeholders():
    styles1 = {"color": "red"}
    styles2 = {"font-weight": "bold"}
    # CONSIDER: Is this what we want? Currently, when we have multiple
    # placeholders in a single attribute, we treat it as a string attribute
    # which produces an invalid style attribute.
    with pytest.raises(ValueError):
        _ = to_html(t"<p style='{styles1} {styles2}'>Warning!</p>")


def test_interpolated_style_attribute_merged():
    styles1 = {"color": "red"}
    styles2 = {"font-weight": "bold"}
    res = to_html(t"<p style={styles1} style={styles2}>Warning!</p>")
    assert res == '<p style="color: red; font-weight: bold">Warning!</p>'


def test_interpolated_style_attribute_merged_override():
    styles1 = {"color": "red", "font-weight": "normal"}
    styles2 = {"font-weight": "bold"}
    res = to_html(t"<p style={styles1} style={styles2}>Warning!</p>")
    assert res == '<p style="color: red; font-weight: bold">Warning!</p>'


def test_style_attribute_str():
    styles = "color: red; font-weight: bold;"
    res = to_html(t"<p style={styles}>Warning!</p>")
    assert res == '<p style="color: red; font-weight: bold">Warning!</p>'


def test_style_attribute_non_str_non_dict():
    with pytest.raises(TypeError):
        styles = [1, 2]
        _ = to_html(t"<p style={styles}>Warning!</p>")


def test_style_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    res = to_html(t'<p style="invalid;invalid:" id={"resolved"}></p>')
    assert res == '<p style="invalid;invalid:" id="resolved"></p>', (
        "A single literal attribute should bypass style accumulator."
    )


def test_style_none():
    styles = None
    res = to_html(t"<p style={styles}></p>")
    assert res == "<p></p>"


# --------------------------------------------------------------------------
# Function component interpolation tests
# --------------------------------------------------------------------------


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


def test_interpolated_template_component():
    res = to_html(
        t'<{FunctionComponent} first=1 second={99} third-arg="comp1" class="my-comp">Hello, Component!</{FunctionComponent}>'
    )
    assert (
        res
        == '<div id="comp1" data-first="1" data-second="99" class="my-comp">Component: Hello, Component!</div>'
    )


def test_interpolated_template_component_no_children_provided():
    """Same test, but the caller didn't provide any children."""
    res = to_html(
        t'<{FunctionComponent} first=1 second={99} third-arg="comp1" class="my-comp" />'
    )
    assert (
        res
        == '<div id="comp1" data-first="1" data-second="99" class="my-comp">Component: </div>'
    )


def test_invalid_component_invocation():
    with pytest.raises(TypeError):
        _ = to_html(t"<{FunctionComponent}>Missing props</{FunctionComponent}>")


def test_prep_component_kwargs_named():
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
def test_prep_component_kwargs_unused_kwargs():
    def InputElement(size=10, type="text"):
        pass

    callable_info = get_callable_info(InputElement)
    with pytest.raises(ValueError):
        assert (
            prep_component_kwargs(callable_info, {"type2": 15}, system_kwargs={}) == {}
        )


def FunctionComponentNoChildren(first: str, second: int, third_arg: str) -> Template:
    # Ensure type correctness of props at runtime for testing purposes
    assert isinstance(first, str)
    assert isinstance(second, int)
    assert isinstance(third_arg, str)
    new_attrs = {
        "id": third_arg,
        "data": {"first": first, "second": second},
    }
    return t"<div {new_attrs}>Component: ignore children</div>"


def test_interpolated_template_component_ignore_children():
    res = to_html(
        t'<{FunctionComponentNoChildren} first=1 second={99} third-arg="comp1">Hello, Component!</{FunctionComponentNoChildren}>'
    )
    assert (
        res
        == '<div id="comp1" data-first="1" data-second="99">Component: ignore children</div>'
    )


def FunctionComponentKeywordArgs(first: str, **attrs: t.Any) -> Template:
    # Ensure type correctness of props at runtime for testing purposes
    assert isinstance(first, str)
    assert "children" in attrs
    _ = attrs.pop("children")
    new_attrs = {"data-first": first, **attrs}
    return t"<div {new_attrs}>Component with kwargs</div>"


def test_children_always_passed_via_kwargs():
    res = to_html(
        t'<{FunctionComponentKeywordArgs} first="value" extra="info">Child content</{FunctionComponentKeywordArgs}>'
    )
    assert res == '<div data-first="value" extra="info">Component with kwargs</div>'


def test_children_always_passed_via_kwargs_even_when_empty():
    res = to_html(t'<{FunctionComponentKeywordArgs} first="value" extra="info" />')
    assert res == '<div data-first="value" extra="info">Component with kwargs</div>'


def ColumnsComponent() -> Template:
    return t"""<td>Column 1</td><td>Column 2</td>"""


def test_fragment_from_component():
    # This test assumes that if a component returns a template that parses
    # into multiple root elements, they are treated as a fragment.
    res = to_html(t"<table><tr><{ColumnsComponent} /></tr></table>")
    assert res == "<table><tr><td>Column 1</td><td>Column 2</td></tr></table>"


def test_component_passed_as_attr_value():
    def Wrapper(
        children: Template, sub_component: t.Callable, **attrs: t.Any
    ) -> Template:
        return t"<{sub_component} {attrs}>{children}</{sub_component}>"

    res = to_html(
        t'<{Wrapper} sub-component={FunctionComponent} class="wrapped" first=1 second={99} third-arg="comp1"><p>Inside wrapper</p></{Wrapper}>'
    )
    assert (
        res
        == '<div id="comp1" data-first="1" data-second="99" class="wrapped">Component: <p>Inside wrapper</p></div>'
    )


def test_nested_component_gh23():
    # @DESIGN: Do we need this?  Should we recommend an alternative?
    # See https://github.com/t-strings/tdom/issues/23 for context
    def Header() -> Template:
        return t"{'Hello World'}"

    res = to_html(t"<{Header} />", last_parent_tag="div")
    assert res == "Hello World"


# @DESIGN: This seems to complicate component definitions.
# Worst case we can just return an iterable in a template interpolation.
@pytest.mark.skip(
    "This seems to make component definitions more confusing.  Marking skip to then rewrite or remove."
)
def test_component_returning_iterable():
    def generate_lis() -> t.Iterable:
        for i in range(2):
            yield t"<li>Item {i + 1}</li>"
        yield t"<li>Item {3}</li>"

    def Items() -> Template:
        return t"{generate_lis()}"

    res = to_html(t"<ul><{Items} /></ul>")
    assert res == "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"


def test_component_returning_fragment():
    def Items() -> Template:
        return t"<li>Item {1}</li><li>Item {2}</li><li>Item {3}</li>"

    res = to_html(t"<ul><{Items} /></ul>")
    assert str(res) == "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"


@dataclass
class ClassComponent:
    """Example class-based component."""

    user_name: str
    image_url: str
    homepage: str = "#"
    children: Template | None = None

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


def test_class_component_implicit_invocation_with_children():
    res = to_html(
        t"<{ClassComponent} user-name='Alice' image-url='https://example.com/alice.png'>Fun times!</{ClassComponent}>"
    )
    assert (
        res
        == '<div class="avatar"><a href="#"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span>Fun times!</div>'
    )


def test_class_component_direct_invocation():
    avatar = ClassComponent(
        user_name="Alice",
        image_url="https://example.com/alice.png",
        homepage="https://example.com/users/alice",
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


def test_class_component_implicit_invocation_ignore_children():
    res = to_html(
        t"<{ClassComponentNoChildren} user-name='Alice' image-url='https://example.com/alice.png'>Fun times!</{ClassComponentNoChildren}>"
    )
    assert (
        res
        == '<div class="avatar"><a href="#"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span>ignore children</div>'
    )


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


def test_attribute_type_component():
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


def test_component_non_callable_fails():
    with pytest.raises(TypeError):
        _ = to_html(t"<{'not a function'} />")


def RequiresPositional(whoops: int, /) -> Template:  # pragma: no cover
    return t"<p>Positional arg: {whoops}</p>"


def test_component_requiring_positional_arg_fails():
    with pytest.raises(TypeError):
        _ = to_html(t"<{RequiresPositional} />")


def test_mismatched_component_closing_tag_fails():
    with pytest.raises(TypeError):
        _ = to_html(
            t"<{FunctionComponent} first=1 second={99} third-arg='comp1'>Hello</{ClassComponent}>"
        )
