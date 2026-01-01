from .transformer import render_service_factory
from contextvars import ContextVar
from string.templatelib import Template


theme_context_var = ContextVar('theme', default='default')


def test_render_template_repeated():
    def get_sample_t(idx, spread_attrs, button_text):
        return t'''<div><button data-key={idx} {spread_attrs}>{button_text}</button></div>'''
    render_api = render_service_factory()
    struct_cache = {}
    for idx in range(3):
        spread_attrs = {'data-enabled': True}
        button_text = 'RENDER'
        sample_t = get_sample_t(idx, spread_attrs, button_text)
        assert render_api.render_template(sample_t, struct_cache) == f'<div><button data-key="{idx}" data-enabled>RENDER</button></div>'

def test_render_template_iterables():
    render_api = render_service_factory()

    def get_select_t_with_list(options, selected_values):
        return t'''<select>{[
            t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>" for opt in options]
        }</select>'''
    def get_select_t_with_generator(options, selected_values):
        return t'''<select>{(
            t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>" for opt in options)
        }</select>'''
    def get_select_t_with_concat(options, selected_values):
        parts = [t'<select>']
        parts.extend([t"<option value={opt[0]} selected={opt[0] in selected_values}>{opt[1]}</option>" for opt in options])
        parts.append(t'</select>')
        return sum(parts, t"")

    def get_color_select_t(selected_values: set, provider: Callable) -> Template:
        PRIMARY_COLORS = [("R", "Red"), ("Y", "Yellow"), ("B", "Blue")]
        assert set(selected_values).issubset(set([opt[0] for opt in PRIMARY_COLORS]))
        return provider(PRIMARY_COLORS, selected_values)

    struct_cache = {}
    for provider in (get_select_t_with_list,get_select_t_with_generator,get_select_t_with_concat):
        assert render_api.render_template(get_color_select_t(set(), provider), struct_cache) == '<select><option value="R">Red</option><option value="Y">Yellow</option><option value="B">Blue</option></select>'
        assert render_api.render_template(get_color_select_t({'Y'}, provider), struct_cache) == '<select><option value="R">Red</option><option value="Y" selected>Yellow</option><option value="B">Blue</option></select>'


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

