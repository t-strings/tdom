from .transformer import render_service_factory


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

from contextvars import ContextVar


theme_context_var = ContextVar('theme', default='default')


def test_component():

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
