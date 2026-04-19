# Static String

Let's look at some non-dynamic uses of templating to learn the basics.

## Render a String Literal

Let's start with the simplest form of templating: just a string, no tags, no
attributes:

<!-- invisible-code-block: python
from tdom import html
-->

```python
result = html(t"Hello World")
assert result == 'Hello World'
```

We start by importing the `html` function from `tdom`.

It takes a [Python 3.14 t-string](https://t-strings.help/introduction.html) and
returns a `str()`.

## Simple Render

Same thing, but in a `<div>`: nothing dynamic, just "template" a string of HTML,
but done in one step:

```python
result = html(t"<div>Hello World</div>")
assert result == '<div>Hello World</div>'
```

## Interpolations as Attribute Values

We can go one step further with this and use interpolations from PEP 750
t-strings. Let's pass in a Python symbol as part of the template, inside curly
braces:

```python
my_class = "active"
result = html(t'<div class={my_class}>Hello World</div>')
assert result == '<div class="active">Hello World</div>'
```

TODO: describe all the many many ways to express attribute values, including
`tdom`'s special handling of boolean attributes, whole-tag spreads, `class`,
`style`, `data` and `aria` attributes, etc.

## Expressing the Document Type

One last point: the HTML doctype can be a tricky one to get into the template.
In `tdom` this is straightforward:

```python
result = html(t"<!DOCTYPE html><div>Hello World</div>")
assert result == '<!DOCTYPE html><div>Hello World</div>'
```

## Reducing Boolean Attribute Values

The renderer also knows how to collapse truthy-y values into simplified HTML
attributes. Thus, instead of `editable="1"` you just get the attribute _name_
without a _value_:

```python
result = html(t"<div editable={True}>Hello World</div>")
assert result == '<div editable>Hello World</div>'
```
