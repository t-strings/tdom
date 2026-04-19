from string.templatelib import Template

from tdom import html, svg

# svg() — tag case-fixing


def test_svg_clippath_case_fixed():
    result = svg(t"<clipPath id='mask'></clipPath>")
    assert result == '<clipPath id="mask"></clipPath>'


def test_svg_lineargradient_case_fixed():
    result = svg(t"<linearGradient id='grad'></linearGradient>")
    assert result == '<linearGradient id="grad"></linearGradient>'


def test_svg_femergenode_self_closing_case_fixed():
    result = svg(t"<feMergeNode />")
    assert result == "<feMergeNode></feMergeNode>"


def test_svg_nested_tags_case_fixed():
    result = svg(t"<g><clipPath id='c'><rect /></clipPath></g>")
    assert result == '<g><clipPath id="c"><rect></rect></clipPath></g>'


# ------------------------------
# svg() — attribute case-fixing
# ------------------------------


def test_svg_viewbox_attr_case_fixed():
    result = svg(t'<rect viewBox="0 0 10 10" />')
    assert result == '<rect viewBox="0 0 10 10"></rect>'


def test_svg_case_sensitivity():
    # SVG attributes like viewBox are case-sensitive
    result = html(t'<svg viewBox="0 0 100 100"></svg>')
    # We expect viewBox, not viewbox
    assert "viewBox" in result


def test_svg_tag_case_sensitivity():
    # SVG tags like linearGradient are case-sensitive
    result = html(t"<svg><linearGradient></linearGradient></svg>")
    assert "linearGradient" in result


def test_svg_tag_case_sensitivity_outside_svg():
    # Outside SVG, tags should be lowercased
    result = html(t"<linearGradient></linearGradient>")
    assert "lineargradient" in result


def test_svg_attr_case_sensitivity_outside_svg():
    # Outside SVG, attributes should be lowercased
    result = html(t'<div viewBox="0 0 100 100"></div>')
    assert "viewbox" in result


def test_svg_interpolated_attr():
    cx, cy, r = 50, 50, 40
    result = svg(t'<circle cx="{cx}" cy="{cy}" r="{r}" />')
    assert result == '<circle cx="50" cy="50" r="40"></circle>'


def test_svg_interpolated_child():
    label = "hello"
    result = svg(t"<text>{label}</text>")
    assert result == "<text>hello</text>"


def test_svg_fragment_multiple_roots():
    result = svg(t"<circle /><rect />")
    assert result == "<circle></circle><rect></rect>"


# ---------------------------------------------------------
# svg() vs html() — same strings, distinct parse results
# ---------------------------------------------------------


def test_svg_and_html_produce_different_results_for_same_strings():
    # html() lowercases clipPath (no SVG context); svg() preserves it.
    html_result = html(t"<clipPath></clipPath>")
    svg_result = svg(t"<clipPath></clipPath>")
    assert html_result == "<clippath></clippath>"
    assert svg_result == "<clipPath></clipPath>"


def test_html_full_svg_document_still_works():
    # html() auto-detects SVG context when <svg> is present — no regression.
    result = html(t"<svg><clipPath id='c'></clipPath></svg>")
    assert result == '<svg><clipPath id="c"></clipPath></svg>'


# -------------------------------
# svg() composable inside html()
# -------------------------------


def test_svg_fragment_embedded_in_html():
    def icon() -> Template:
        return t'<rect viewBox="0 0 10 10" />'

    result = html(t'<div class="icon"><svg>{icon()}</svg></div>')
    assert (
        result == '<div class="icon"><svg><rect viewBox="0 0 10 10"></rect></svg></div>'
    )


def test_svg_fragment_with_spread_attr():
    def icon(attrs: dict[str, str]) -> Template:
        return t"<rect {attrs} />"

    rect_attrs = {"viewbox": "0 0 10 10"}
    result = html(t'<div class="icon"><svg>{icon(attrs=rect_attrs)}</svg></div>')
    assert (
        result == '<div class="icon"><svg><rect viewBox="0 0 10 10"></rect></svg></div>'
    )


def test_svg_nesting():
    svg_doc = t"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf8">
  </head>
  <body>
  <svg width=1000 height=1000>
  <rect width="100%" height="100%" fill="red"></rect>
    <foreignObject width=500 height=500>
      text,fo,svg,html
      <div>
          <!-- This should be lowercased because it is actually in HTML. -->
          <foreignObject></foreignObject>
          text,div,fo,svg,html
          <svg width=300 height=300>
            <rect width="100%" height="100%" fill="blue"></rect>
            <circle cx=50 cy=50 r="15" fill="green"></circle>
            <foreignObject width=100 height=100>
              <span style="font-size: 10px">text,span,fo,svg,div,fo,svg,html</span>
            </foreignObject>
          </svg>
          <math><mi>&pi;</mi></math>
        </div>
      </foreignObject>
    </svg>
  </body>
</html>"""
    res = html(svg_doc)
    assert res.count("<foreignObject") == 2
