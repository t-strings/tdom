import pytest

from tdom import html, svg


# svg() — tag case-fixing

def test_svg_clippath_case_fixed():
    node = svg(t"<clipPath id='mask'></clipPath>")
    assert str(node) == '<clipPath id="mask"></clipPath>'


def test_svg_lineargradient_case_fixed():
    node = svg(t"<linearGradient id='grad'></linearGradient>")
    assert str(node) == '<linearGradient id="grad"></linearGradient>'


def test_svg_femergenode_self_closing_case_fixed():
    node = svg(t"<feMergeNode />")
    assert str(node) == "<feMergeNode></feMergeNode>"


def test_svg_nested_tags_case_fixed():
    node = svg(t"<g><clipPath id='c'><rect /></clipPath></g>")
    assert str(node) == '<g><clipPath id="c"><rect></rect></clipPath></g>'


# ------------------------------
# svg() — attribute case-fixing
# ------------------------------


def test_svg_viewbox_attr_case_fixed():
    node = svg(t'<rect viewBox="0 0 10 10" />')
    assert str(node) == '<rect viewBox="0 0 10 10"></rect>'

def test_svg_case_sensitivity():
    # SVG attributes like viewBox are case-sensitive
    node = html(t'<svg viewBox="0 0 100 100"></svg>')
    # We expect viewBox, not viewbox
    assert 'viewBox' in str(node)

def test_svg_tag_case_sensitivity():
    # SVG tags like linearGradient are case-sensitive
    node = html(t'<svg><linearGradient></linearGradient></svg>')
    assert 'linearGradient' in str(node)

def test_svg_tag_case_sensitivity_outside_svg():
    # Outside SVG, tags should be lowercased
    node = html(t'<linearGradient></linearGradient>')
    assert 'lineargradient' in str(node)

def test_svg_attr_case_sensitivity_outside_svg():
    # Outside SVG, attributes should be lowercased
    node = html(t'<div viewBox="0 0 100 100"></div>')
    assert 'viewbox' in str(node)

def test_svg_interpolated_attr():
    cx, cy, r = 50, 50, 40
    node = svg(t'<circle cx="{cx}" cy="{cy}" r="{r}" />')
    assert str(node) == '<circle cx="50" cy="50" r="40"></circle>'


def test_svg_interpolated_child():
    label = "hello"
    node = svg(t"<text>{label}</text>")
    assert str(node) == "<text>hello</text>"


def test_svg_fragment_multiple_roots():
    node = svg(t"<circle /><rect />")
    assert str(node) == "<circle></circle><rect></rect>"


# ---------------------------------------------------------
# svg() vs html() — same strings, distinct parse results
# ---------------------------------------------------------


def test_svg_and_html_produce_different_results_for_same_strings():
    # html() lowercases clipPath (no SVG context); svg() preserves it.
    html_node = html(t"<clipPath></clipPath>")
    svg_node = svg(t"<clipPath></clipPath>")
    assert str(html_node) == "<clippath></clippath>"
    assert str(svg_node) == "<clipPath></clipPath>"


def test_html_full_svg_document_still_works():
    # html() auto-detects SVG context when <svg> is present — no regression.
    node = html(t"<svg><clipPath id='c'></clipPath></svg>")
    assert str(node) == '<svg><clipPath id="c"></clipPath></svg>'


# -------------------------------
# svg() composable inside html()
# -------------------------------


def test_svg_fragment_embedded_in_html():
    def icon():
        return svg(t'<circle cx="50" cy="50" r="40" />')

    node = html(t'<div class="icon"><svg>{icon()}</svg></div>')
    assert str(node) == '<div class="icon"><svg><circle cx="50" cy="50" r="40"></circle></svg></div>'
