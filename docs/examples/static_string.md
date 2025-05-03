# Static String

Let's look at some non-dynamic uses of templating to learn the basics.

## Render a String Literal

Let's start with the simplest form of templating: just a string, no tags, no attributes:

```{literalinclude} ../../examples/static_string/string_literal/__init__.py
---
start-at: from tdom import html
---
```

We start by importing the `html` function from `tdom`.
It takes a Python 3.14 t-string and returns a `Node` with an `__str__` that converts to HTML. In this case, the node is
an instance of `tdom.dom.Text`, a subclass of `Node`.

## Simple Render

Same thing, but in a `<div>`: nothing dynamic, just "template" a string of HTML, but done in one step:

```{literalinclude} ../../examples/static_string/simple_render/__init__.py
---
start-at: def main
---
```

## Show the Node Itself

Let's take a look at that `Node` structure.
This time, we'll inspect the node rather than rendering it to a string:

```{literalinclude} ../../examples/static_string/show_vdom/__init__.py
---
start-at: def main
---
```

In our test we see that we got back an `Element`:

```{literalinclude} ../../examples/static_string/show_vdom/test_show_vdom.py
---
start-at: assert
---
```

What does it look like?

- The `result` is of type `tdom.dom.Element` (a subclass of `Node`)
-
- The name of the node (`<div>`)

- The properties passed to that tag (in this case, `{"class": "container"}`)

- The children of this tag (in this case, a `Text` node of `Hello World`)

## Interpolations as Attribute Values

We can go one step further with this and use interpolations from PEP 750 t-strings.
Let's pass in a Python symbol as part of the template, inside curly braces:

```{literalinclude} ../../examples/static_string/expressions_as_values/__init__.py
---
start-at: def main
---
```

Everything is the same, except the value of the `class` prop now has a Python `int` included in the string.

```{literalinclude} ../../examples/static_string/expressions_as_values/test_expressions_as_values.py
---
start-at: assert
---
```

If it looks like Python `f-strings`, well, that's the point.
We did an expression _inside_ that prop value, using a Python expression that evaluated to just the number `1`.

## Shorthand Syntax

As shorthand, when the entire attribute value is an expression, you can use curly braces instead of putting in
double quotes:

```{literalinclude} ../../examples/static_string/shorthand_syntax/__init__.py
---
start-at: def main
---
```

## Child Nodes in an `Element`

Let's look at what more nesting would look like:

```{literalinclude} ../../examples/static_string/child_nodes/__init__.py
---
start-at: def main
---
```

Over in the test, we see what this looks like:

```{literalinclude} ../../examples/static_string/child_nodes/test_child_nodes.py
---
start-at: assert
---
```

It's a nested Python datastructure -- pretty simple to look at.

## Reducing Boolean Attribute Values

The renderer also knows how to collapse truthy-y values into simplified HTML attributes.
Thus, instead of `editable="1"` you just get the attribute _name_ without a _value_:

```{literalinclude} ../../examples/static_string/boolean_attribute_value/__init__.py
---
start-at: def main
---
```

The result is transformed by `tdom` into a simpler HTML boolean representation:

```{literalinclude} ../../examples/static_string/boolean_attribute_value/test_boolean_attribute_value.py
---
start-at: assert
---
```