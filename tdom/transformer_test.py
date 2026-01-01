from .transformer import render_service_factory
from contextvars import ContextVar


theme_context_var = ContextVar('theme', default='default')


def test_render_template():
    def get_sample_t(idx, spread_attrs, button_text):
        return t'''<div><button data-key={idx} {spread_attrs}>{button_text}</button></div>'''
    render_api = render_service_factory()
    struct_cache = {}
    for count in (1, 1, 100):
        for idx in range(count):
            spread_attrs = {'data-enabled': True}
            button_text = 'RENDER'
            sample_t = get_sample_t(idx, spread_attrs, button_text)
            assert ''.join(render_api.render_template(sample_t, struct_cache)) == f'<div><button data-key="{idx}" data-enabled>RENDER</button></div>'

    new_sample_t = get_sample_t("zebra", {"diff": "yes"}, t"<div>{sample_t}</div>") # You dirty dog! Stay. In. Your. Scope.
    assert ''.join(render_api.render_template(new_sample_t, struct_cache)) == \
        f'<div><button data-key="zebra" diff="yes"><div><div><button data-key="99" data-enabled>RENDER</button></div></div></button></div>'

def test_render_select():
    render_api = render_service_factory()

    def get_select_t(options, selected_values):
        return t'''<select>{[
            t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>" for opt in options]
        }</select>'''

    def get_color_select_t(selected_values: set) -> Template:
        PRIMARY_COLORS = [("R", "Red"), ("Y", "Yellow"), ("B", "Blue")]
        assert set(selected_values).issubset(set([opt[0] for opt in PRIMARY_COLORS]))
        return get_select_t(PRIMARY_COLORS, selected_values)

    struct_cache = {}
    assert render_api.render_template(get_color_select_t(set()), struct_cache) == '<select><option value="R">Red</option><option value="Y">Yellow</option><option value="B">Blue</option></select>'
    assert render_api.render_template(get_color_select_t({'Y'}), struct_cache) == '<select><option value="R">Red</option><option value="Y" selected>Yellow</option><option value="B">Blue</option></select>'







def test_render_component_with_context():

    def ThemeContext(attrs, embedded_t, embedded_struct):
        context_values = ((theme_context_var, attrs.get('value', 'normal')),)
        return embedded_t, context_values

    def ThemedDiv(attrs, embedded_t, embedded_struct):
        theme = theme_context_var.get()
        return t'<div data-theme="{theme}">{embedded_t}</div>', ()

    render_api = render_service_factory()
    body_t = t"<div><{ThemeContext} value='holiday'><{ThemedDiv}><b>Cheers!</b></{ThemedDiv}></{ThemeContext}></div>"
    with theme_context_var.set('not-the-default'):
        assert render_api.render_template(body_t) == '<div><div data-theme="holiday"><b>Cheers!</b></div></div>'
        assert theme_context_var.get() == 'not-the-default'
    assert theme_context_var.get() == 'default'


def test_render_template_components_smoketest():

    def PageComponent(attrs, content_t, content_struct):
        return t'''<div class="content">{content_t}</div>''', ()

    def FooterComponent(attrs, body_t, body_struct):
        return t'<div class="footer"><a href="about">About</a></div>', ()

    def LayoutComponent(attrs, body_t, body_struct):
        return t'''<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>{body_t}<{FooterComponent} /></body>
</html>
''', ()

    render_api = render_service_factory()
    content = 'HTML never goes out of style.'
    content_str = render_api.render_template(t'<{LayoutComponent}><{PageComponent}>{content}</{PageComponent}></{LayoutComponent}>')
    assert content_str == '''<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body><div class="content">HTML never goes out of style.</div><div class="footer"><a href="about">About</a></div></body>
</html>
'''


def test_render_template_functions_smoketest():

    def make_page_t(content: str) -> Template:
        return t'''<div class="content">{content}</div>'''

    def make_footer_t() -> Template:
        return t'<div class="footer"><a href="about">About</a></div>'

    def make_layout_t(body_t: Template) -> Template:
        footer_t = make_footer_t()
        return t'''<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>{body_t}{footer_t}</body>
</html>
'''

    render_api = render_service_factory()
    content = 'HTML never goes out of style.'
    layout_t = make_layout_t(make_page_t(content))
    content_str = render_api.render_template(layout_t)
    assert content_str == '''<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="scripts.js"></script>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body><div class="content">HTML never goes out of style.</div><div class="footer"><a href="about">About</a></div></body>
</html>
'''

