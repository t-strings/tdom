# Static String

Let's look at some non-dynamic uses of templating to learn the basics.

## Render a String Literal

Let's start with the simplest form of templating: just a string, no tags, no attributes:
For the purposes of illustration, we do the VDOM in one step and the rendering in a second.

```{literalinclude} ../../examples/static_string/string_literal/__init__.py
---
start-at: from tdom import html
---
```

We start by importing the `html` function from `tdom`.
It takes a Python 3.14 t-string and returns a VDOM with an `__str__` that converts to HTML.

## Simple Render

Same thing, but in a `<div>`: nothing dynamic, just "template" a string of HTML, but done in one step:

```{literalinclude} ../../examples/static_string/simple_render/__init__.py
---
start-at: def main
---
```

We get back a `DOM` with:

- The name of the "tag" (`<div>`)

- The properties passed to that tag (in this case, an empty dict)

- The children of this tag (in this case, a text node of `Hello World`)

The second item in the VDOM tuple -- the props dictionary -- now has a key of 'class' with the assigned class name value.

## Show the VDOM Itself

Let's take a look at that VDOM structure.
This time, we'll return the VDOM rather than rendering it to a string:

```{literalinclude} ../../examples/static_string/show_vdom/__init__.py
---
start-at: def main
---
```

In our test we see that we got back a `VDOM` -- an optimized dataclass:

```{literalinclude} ../../examples/static_string/show_vdom/test_show_vdom.py
---
start-at: assert
---
```

What does it look like?

- The name of the "tag" (`<div>`)

- The properties passed to that tag (in this case, an empty dict)

- The children of this tag (in this case, a text node of `Hello World`)

The second item in the VDOM tuple -- the props dictionary -- now has a key of 'class' with the assigned class name value.

## Expressions as Attribute Values

We can go one step further with this and use a little bit of "expressions".
Let's pass in a Python symbol as part of the template, inside curly braces:

```{literalinclude} ../../examples/static_string/expressions_as_values/__init__.py
---
start-at: def main
---
```

Everything is the same, except the value of the `class` prop now has a Python `int` included in the string.
If it looks like Python `f-strings`, well, that's the point.
We did an expression _inside_ that prop value, using a Python expression that evaluated to just the number `1`.

## Shorthand Syntax

As shorthand, when the entire attribute value is an expression, you can just use curly braces instead of putting in double quotes:

```{literalinclude} ../../examples/static_string/shorthand_syntax/__init__.py
---
start-at: def main
---
```

The VDOM's third item contains the "children".

## Child Nodes in VDOM

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

## Expressing the Doctype

One last point: the HTML doctype is a tricky one to get into the template itself as its syntax is brackety like tags.
Instead, define it as a variable using `markupsafe.Markup` and insert the variable into the template:

```{literalinclude} ../../examples/static_string/doctype/__init__.py
---
start-at: def main
---
```

## Reducing Boolean Attribute Values

The renderer also knows to collapse truthy-y values into simplified HTML attributes.
Thus, instead of `editable="1"` you just get the attribute _name_ without a _value_:

```{literalinclude} ../../examples/static_string/boolean_attribute_value/__init__.py
---
start-at: def main
---
```
