from string.templatelib import Template
from markupsafe import Markup, escape as markupsafe_escape
import typing as t
import pytest
from dataclasses import dataclass
from collections.abc import Callable
from itertools import chain

from .processor import (
    process_service_factory,
    cached_process_service_factory,
    CachedTransformService,
    ProcessService,
    TransformService,
    to_html,
)


def test_process_template_smoketest():
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
    process_api = process_service_factory()
    assert process_api.process_template(smoke_t) == smoke_str


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
    process_api = process_service_factory()
    cached_process_api = cached_process_service_factory()
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


def test_process_template_repeated():
    """Crude check for any unintended state being kept between calls."""

    def get_sample_t(idx, spread_attrs, button_text):
        return t"""<div><button data-key={idx} {spread_attrs}>{button_text}</button></div>"""

    process_apis = (process_service_factory(), cached_process_service_factory())
    for process_api in process_apis:
        for idx in range(3):
            spread_attrs = {"data-enabled": True}
            button_text = "PROCESS"
            sample_t = get_sample_t(idx, spread_attrs, button_text)
            assert (
                process_api.process_template(sample_t)
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


@pytest.mark.parametrize(
    "provider",
    (
        get_select_t_with_list,
        get_select_t_with_generator,
        get_select_t_with_concat,
    ),
)
def test_process_template_iterables(provider):
    process_api = process_service_factory()

    def get_color_select_t(selected_values: set, provider: t.Callable) -> Template:
        PRIMARY_COLORS = [("R", "Red"), ("Y", "Yellow"), ("B", "Blue")]
        assert set(selected_values).issubset(set([opt[0] for opt in PRIMARY_COLORS]))
        return provider(PRIMARY_COLORS, selected_values)

    no_selection_t = get_color_select_t(set(), provider)
    assert (
        process_api.process_template(no_selection_t)
        == '<select><option value="R">Red</option><option value="Y">Yellow</option><option value="B">Blue</option></select>'
    )
    selected_yellow_t = get_color_select_t({"Y"}, provider)
    assert (
        process_api.process_template(selected_yellow_t)
        == '<select><option value="R">Red</option><option value="Y" selected>Yellow</option><option value="B">Blue</option></select>'
    )


def test_process_template_components_smoketest():
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

    process_api = process_service_factory()
    content = "HTML never goes out of style."
    content_str = process_api.process_template(
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


def test_process_template_functions_smoketest():
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

    process_api = process_service_factory()
    content = "HTML never goes out of style."
    layout_t = make_layout_t(make_page_t(content), "theme-default")
    content_str = process_api.process_template(layout_t)
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
    process_api = process_service_factory()
    with pytest.raises(
        ValueError, match="Recursive includes are not supported within script"
    ):
        content = '<script>console.log("123!");</script>'
        content_t = t"{content}"
        _ = process_api.process_template(t"<script>{content_t}</script>")


@pytest.mark.skip("Can we allow this?")
def test_escape_escapable_raw_text_with_dynamic_parent():
    content = '<script>console.log("123!");</script>'
    content_t = t"{content}"
    process_api = process_service_factory()
    LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
    assert (
        process_api.process_template(t"<textarea>{content_t}</textarea>")
        == f"<textarea>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</textarea>"
    )


def test_escape_structured_text_with_dynamic_parent():
    content = '<script>console.log("123!");</script>'
    content_t = t"{content}"
    process_api = process_service_factory()
    LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
    assert (
        process_api.process_template(t"<div>{content_t}</div>")
        == f"<div>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</div>"
    )


def test_escape_structured_text():
    content = '<script>console.log("123!");</script>'
    content_t = t"<div>{content}</div>"
    process_api = process_service_factory()
    LT, GT, DQ = map(markupsafe_escape, ["<", ">", '"'])
    assert (
        process_api.process_template(content_t)
        == f"<div>{LT}script{GT}console.log({DQ}123!{DQ});{LT}/script{GT}</div>"
    )


@dataclass
class Pager:
    left_pages: tuple = ()
    page: int = 0
    right_pages: tuple = ()
    prev_page: int | None = None
    next_page: int | None = None


@dataclass
class PagerDisplay:
    pager: Pager
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


def test_class_component():
    def paginate_url(page: int) -> str:
        return f"/pages?page={page}"

    def Footer(pager, paginate_url, footer_classes=("footer",)) -> Template:
        return t"<div class={footer_classes}><{PagerDisplay} pager={pager} paginate_url={paginate_url} /></div>"

    pager = Pager(
        left_pages=(1, 2), page=3, right_pages=(4, 5), next_page=6, prev_page=None
    )
    content_t = t"<{Footer} pager={pager} paginate_url={paginate_url} />"
    process_api = process_service_factory()
    res = process_api.process_template(content_t)
    print(res)
    assert (
        res
        == '<div class="footer"><div class="cb tc w-100"><a href="/pages?page=1" class="dib pa1">1</a><a href="/pages?page=2" class="dib pa1">2</a><span class="dib pa1">3</span><a href="/pages?page=4" class="dib pa1">4</a><a href="/pages?page=5" class="dib pa1">5</a><a href="/pages?page=6" class="dib pa1">Next</a></div></div>'
    )


def test_mathml():
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
    process_api = process_service_factory()
    res = process_api.process_template(mathml_t)
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


def test_svg():
    cx, cy, r, fill = 150, 100, 80, "green"
    svg_t = t"""<svg version="1.1" width="300" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="red" />
  <circle cx={cx} cy={cy} r={r} fill={fill} />
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    process_api = process_service_factory()
    res = process_api.process_template(svg_t)
    assert (
        str(res)
        == """<svg version="1.1" width="300" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="red"></rect>
  <circle cx="150" cy="100" r="80" fill="green"></circle>
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    )


@pytest.mark.skip("""Need foreign element mode.  Could work like last parent.""")
def test_svg_self_closing_empty_elements():
    cx, cy, r, fill = 150, 100, 80, "green"
    svg_t = t"""<svg width="300" height="200">
  <rect width="100%" height="100%" fill="red" />
  <circle cx={cx} cy={cy} r={r} fill={fill} />
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    process_api = process_service_factory()
    res = process_api.process_template(svg_t)
    assert (
        str(res)
        == """<svg width="300" height="200">
  <rect width="100%" height="100%" fill="red" />
  <circle cx="150" cy="100" r="80" fill="green" />
  <text x="150" y="125" font-size="60" text-anchor="middle" fill="white">SVG</text>
</svg>"""
    )


@dataclass
class FakeUser:
    name: str
    id: int


@dataclass
class FakeRequest:
    user: FakeUser | None = None


@dataclass(frozen=True)
class RequestProcessService(ProcessService):
    request: FakeRequest | None = None

    def get_system(self, **kwargs):
        return {**kwargs, "request": self.request}


class UserProto(t.Protocol):
    name: str


class RequestProto(t.Protocol):
    user: UserProto | None


def test_system_context():
    """Test providing context to components horizontally via *extra* system provided kwargs."""

    def request_process_api(request):
        return RequestProcessService(request=request, transform_api=TransformService())

    def UserStatus(request: RequestProto, children: Template | None = None) -> Template:
        user = request.user
        if user:
            classes = ("account-online",)
            status_t = t"<span>Logged in as {user.name}</span>"
        else:
            classes = ("account-offline",)
            status_t = t"<span>Not logged in</span>"
        return t"<div class=account class={classes}>{children}{status_t}</div>"

    page_t = t"""<!doctype html><html><body><div class=header><{UserStatus}><span class=account-icon>&#x1F464;</span></{UserStatus}></div></body></html>"""
    process_api = request_process_api(FakeRequest(user=FakeUser(name="Guido", id=1000)))
    res = process_api.process_template(page_t)
    assert (
        res
        == """<!doctype html><html><body><div class="header"><div class="account account-online"><span class="account-icon">👤</span><span>Logged in as Guido</span></div></div></body></html>"""
    )
    process_api = request_process_api(FakeRequest(user=None))
    res = process_api.process_template(page_t)
    assert (
        res
        == """<!doctype html><html><body><div class="header"><div class="account account-offline"><span class="account-icon">👤</span><span>Not logged in</span></div></div></body></html>"""
    )

    process_api = ProcessService(transform_api=TransformService())
    with pytest.raises(TypeError) as excinfo:
        res = process_api.process_template(page_t)
    assert "Missing required parameters" in str(excinfo.value)


def test_to_html():
    assert to_html(t"<input>") == "<input />"
    assert to_html(t"<!doctype html>") == "<!DOCTYPE html>"
    assert to_html(t"<div>{'content'}</div>") == "<div>content</div>"
