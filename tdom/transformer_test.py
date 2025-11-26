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
