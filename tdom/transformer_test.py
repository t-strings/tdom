from contextvars import ContextVar
from string.templatelib import Template
from markupsafe import Markup, escape as markupsafe_escape
import typing as t
import pytest

from .transformer import (
    render_service_factory,
    cached_render_service_factory,
    CachedTransformService,
)


THEME_CTX = ContextVar("theme", default="default")


def test_render_template_smoketest():
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
    smoke_str = """<!doctype html>
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
    render_api = render_service_factory()
    assert render_api.render_template(smoke_t) == smoke_str


def struct_repr(st):
    """Breakdown Templates into comparable parts for test verification."""
    return st.strings, tuple(
        [
            (i.value, i.expression, i.conversion, i.format_spec)
            for i in st.interpolations
        ]
    )


def test_process_template_internal_cache():
    """Test that cache and non-cache both generally work as expected."""
    sample_t = t"""<div>{"content"}</div>"""
    sample_diff_t = t"""<div>{"diffcontent"}</div>"""
    alt_t = t"""<span>{"content"}</span>"""
    render_api = render_service_factory()
    cached_render_api = cached_render_service_factory()
    tnode1 = render_api.transform_api.transform_template(sample_t)
    tnode2 = render_api.transform_api.transform_template(sample_t)
    cached_tnode1 = cached_render_api.transform_api.transform_template(sample_t)
    cached_tnode2 = cached_render_api.transform_api.transform_template(sample_t)
    cached_tnode3 = cached_render_api.transform_api.transform_template(sample_diff_t)
    # Check that the uncached and cached services are actually
    # returning non-identical results.
    assert tnode1 is not cached_tnode1
    assert tnode1 is not cached_tnode2
    assert tnode1 is not cached_tnode3
    # Check that the uncached service returns a brand new result everytime.
    assert tnode1 is not tnode2
    # Check that the cached service is returning the exact same, identical, result.
    assert cached_tnode1 is cached_tnode2
    # Even if the input templates are not identical (but are still equivalent).
    assert cached_tnode1 is cached_tnode3 and sample_t is not sample_diff_t
    # Check that the cached service and uncached services return
    # results that are equivalent (even though they are not (id)entical).
    assert struct_repr(tnode1) == struct_repr(cached_tnode1)
    assert struct_repr(tnode2) == struct_repr(cached_tnode1)
    # Technically this could be the superclass which doesn't have cached method.
    assert isinstance(cached_render_api.transform_api, CachedTransformService)
    # Now that we are setup we check that the cache is internally
    # working as we intended.
    ci = cached_render_api.transform_api._transform_template.cache_info()
    # cached_tnode2 and cached_tnode3 are hits after cached_tnode1
    assert ci.hits == 2
    # cached_tnode1 was a miss because cache was empty (brand new)
    assert ci.misses == 1
    cached_tnode4 = cached_render_api.transform_api.transform_template(alt_t)
    # A different template produces a brand new tnode.
    assert cached_tnode1 is not cached_tnode4
    # The template is new AND has a different structure so it also
    # produces an unequivalent tnode.
    assert struct_repr(cached_tnode1) != struct_repr(cached_tnode4)


def test_render_template_repeated():
    """Crude check for any unintended state being kept between calls."""

    def get_sample_t(idx, spread_attrs, button_text):
        return t"""<div><button data-key={idx} {spread_attrs}>{button_text}</button></div>"""

    render_apis = (render_service_factory(), cached_render_service_factory())
    for render_api in render_apis:
        for idx in range(3):
            spread_attrs = {"data-enabled": True}
            button_text = "RENDER"
            sample_t = get_sample_t(idx, spread_attrs, button_text)
            assert (
                render_api.render_template(sample_t)
                == f'<div><button data-key="{idx}" data-enabled>RENDER</button></div>'
            )


def test_render_template_iterables():
    render_api = render_service_factory()

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

    def get_color_select_t(selected_values: set, provider: t.Callable) -> Template:
        PRIMARY_COLORS = [("R", "Red"), ("Y", "Yellow"), ("B", "Blue")]
        assert set(selected_values).issubset(set([opt[0] for opt in PRIMARY_COLORS]))
        return provider(PRIMARY_COLORS, selected_values)

    for provider in (
        get_select_t_with_list,
        get_select_t_with_generator,
        get_select_t_with_concat,
    ):
        assert (
            render_api.render_template(get_color_select_t(set(), provider))
            == '<select><option value="R">Red</option><option value="Y">Yellow</option><option value="B">Blue</option></select>'
        )
        assert (
            render_api.render_template(get_color_select_t({"Y"}, provider))
            == '<select><option value="R">Red</option><option value="Y" selected>Yellow</option><option value="B">Blue</option></select>'
        )


def test_context_provider_pattern():
    def ThemeProvider(theme, children):
        return children, {"context_values": ((THEME_CTX, theme),)}

    def IntermediateWrapper(children):
        # Wrap in between the provider and consumer just to make sure there
        # is no direct interaction.
        return t"<div>{children}</div>"

    def ThemeConsumer(children):
        theme = THEME_CTX.get()
        return t'<p data-theme="{theme}">{children}</p>'

    render_api = render_service_factory()
    body_t = t"<body><{ThemeProvider} theme='holiday'><{IntermediateWrapper}><{ThemeConsumer}><b>Cheers!</b></{ThemeConsumer}></{IntermediateWrapper}></{ThemeProvider}></body>"
    # Set the context var to a different value while rendering
    # to make sure this value will be masked
    with THEME_CTX.set("not-the-default"):
        # During rendering the provider should overlay a new value.
        assert (
            render_api.render_template(body_t)
            == '<body><div><p data-theme="holiday"><b>Cheers!</b></p></div></body>'
        )
        # But afterwards we should be back to the old value.
        assert THEME_CTX.get() == "not-the-default"
    # But after all that we should be back to the context var's offical default.
    assert THEME_CTX.get() == "default"


def test_render_template_components_smoketest():
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

    render_api = render_service_factory()
    content = "HTML never goes out of style."
    content_str = render_api.render_template(
        t"<{LayoutComponent} body_classes={['theme-default']}><{PageComponent}>{content}</{PageComponent}></{LayoutComponent}>"
    )
    assert (
        content_str
        == """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body class="theme-default">
    <div class="content">HTML never goes out of style.</div>
    <div class="footer footer-default"><a href="about">About</a></div>
  </body>
</html>
"""
    )


def test_render_template_functions_smoketest():
    """Broadly test that common template function usage works."""

    def make_page_t(content, root_attrs=None) -> Template:
        return t"""<div class="content" {root_attrs}>{content}</div>"""

    def make_footer_t(classes=("footer-default",)) -> Template:
        return t'<div class="footer" class={classes}><a href="about">About</a></div>'

    def make_layout_t(body_t, body_classes=None) -> Template:
        footer_t = make_footer_t()
        return t"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body class={body_classes}>
    {body_t}
    {footer_t}
  </body>
</html>
"""

    render_api = render_service_factory()
    content = "HTML never goes out of style."
    layout_t = make_layout_t(make_page_t(content), "theme-default")
    content_str = render_api.render_template(layout_t)
    assert (
        content_str
        == """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body class="theme-default">
    <div class="content">HTML never goes out of style.</div>
    <div class="footer footer-default"><a href="about">About</a></div>
  </body>
</html>
"""
    )


def test_text_interpolation_with_dynamic_parent():
    render_api = render_service_factory()
    with pytest.raises(
        ValueError, match="Recursive includes are not supported within script"
    ):
        content = '<script>console.log("123!");</script>'
        content_t = t"{content}"
        _ = render_api.render_template(t"<script>{content_t}</script>")


@pytest.mark.skip("Can we allow this?")
def test_escape_escapable_raw_text_with_dynamic_parent():
    content = '<script>console.log("123!");</script>'
    content_t = t"{content}"
    render_api = render_service_factory()
    LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
    assert (
        render_api.render_template(t"<textarea>{content_t}</textarea>")
        == f"<textarea>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</textarea>"
    )


def test_escape_structured_text_with_dynamic_parent():
    content = '<script>console.log("123!");</script>'
    content_t = t"{content}"
    render_api = render_service_factory()
    LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
    assert (
        render_api.render_template(t"<div>{content_t}</div>")
        == f"<div>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</div>"
    )


def test_escape_structured_text():
    content = '<script>console.log("123!");</script>'
    content_t = t"<div>{content}</div>"
    render_api = render_service_factory()
    LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
    assert (
        render_api.render_template(content_t)
        == f"<div>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</div>"
    )
