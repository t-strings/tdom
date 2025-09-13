# Static String

Let's look at some non-dynamic uses of templating to learn the basics.

## Render a String Literal

Let's start with the simplest form of templating: just a string, no tags, no
attributes:

```python
result = html(t"Hello World")
# Hello World
```

We start by importing the `html` function from `tdom`.

It takes a [Python 3.14 t-string](https://t-strings.help/introduction.html) and
returns a `Element` with an `__str__` that converts to HTML. In this case, the
node is an instance of `tdom.nodes.Text`, a subclass of `Element`.

## Simple Render

Same thing, but in a `<div>`: nothing dynamic, just "template" a string of HTML,
but done in one step:

```python
result = html(t"<div>Hello World</div>")
# <div>Hello World</div>
```

## Show the `Element` Itself

Let's take a look at that `Element` structure.

This time, we'll inspect the returned value rather than rendering it to a
string:

```python
from tdom import Element, Text
result = html(t'<div class="container">Hello World</div>')
assert result == Element(
    "div",
    attrs={"class": "container"},
    children=[Text("Hello World")]
)
```

In our test we see that we got back an `Element`. What does it look like?

- The `result` is of type `tdom.nodes.Element` (a subclass of `Node`)
- The name of the node (`<div>`)
- The properties passed to that tag (in this case, `{"class": "container"}`)
- The children of this tag (in this case, a `Text` node of `Hello World`)

## Interpolations as Attribute Values

We can go one step further with this and use interpolations from PEP 750
t-strings. Let's pass in a Python symbol as part of the template, inside curly
braces:

```python
my_class = "active"
result = html(t'<div class={my_class}>Hello World</div>')
# <div class="active">Hello World</div>
```

TODO: describe all the many many ways to express attribute values, including
`tdom`'s special handling of boolean attributes, whole-tag spreads, `class`,
`style`, `data` and `aria` attributes, etc.

## Child Nodes in an `Element`

Let's look at what more nesting would look like:

```python
from tdom import Element, Text
result = html(t"<div>Hello <span>World<em>!</em></span></div>")
assert result == Element(
    "div",
    children=[
        Text("Hello "),
        Element(
            "span",
            children=[
                Text("World"),
                Element("em", children=[Text("!")])
            ]
        )
    ]
)
```

It's a nested Python datastructure -- pretty simple to look at.

## Expressing the Document Type

One last point: the HTML doctype can be a tricky one to get into the template.
In `tdom` this is straightforward:

```python
result = html(t"<!DOCTYPE html><div>Hello World</div>")
# <!DOCTYPE html><div>Hello World</div>
```

## Reducing Boolean Attribute Values

The renderer also knows how to collapse truthy-y values into simplified HTML
attributes. Thus, instead of `editable="1"` you just get the attribute _name_
without a _value_:

```python
result = html(t"<div editable={True}>Hello World</div>")
# <div editable>Hello World</div>
```
