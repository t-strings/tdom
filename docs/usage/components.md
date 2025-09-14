# Components

You often have a snippet of templating that you'd like to re-use.

Many existing templating systems have "macros" for this: units of templating
that can be re-used and called from other templates.

The whole mechanism, though, is quite magical:

- Where do the macros come from? Multiple layers of context magic and specially
  named directories provide the answer.
- What macros are available at the cursor position I'm at in a template? It's
  hard for an editor or IDE to predict and provide autocomplete.
- What are the macros arguments and what is this template's special syntax for
  providing them? And can my editor help on autocomplete or tell me when I got
  it wrong (or the macro changed its signature)?
- How does my current scope interact with the macro's scope, and where does it
  get other parts of its scope from?

The `tdom` package makes this more Pythonic through the use of "components."

Instead of some sorta-callable, a component is a normal Python callable: a
function with normal Python arguments and return values.

## Simple Heading

Here is a component callable &mdash; a `Heading` function &mdash; which returns
a `Node`:

<!-- invisible-code-block: python
from string.templatelib import Template
from tdom import html, ComponentCallable, Node
from typing import Iterable
-->

```python
def Heading() -> Template:
    return t"<h1>My Title</h1>"

result = html(t"<{Heading} />")
assert str(result) == '<h1>My Title</h1>'
```

## Simple Props

As expected, components can have props, passed in as what looks like HTML
attributes. Here we pass a `title` as an argument to `Heading`, using a simple
HTML attribute string value:

```python
def Heading(title: str) -> Template:
    return t"<h1>{title}</h1>"

result = html(t'<{Heading} title="My Title"></{Heading}>')
assert str(result) == '<h1>My Title</h1>'
```

## Children As Props

If your template has children inside the component element, your component will
receive them as `*children` positional arguments:

```python
def Heading(*children: Node, title: str) -> Node:
    return html(t"<h1>{title}</h1><div>{children}</div>")

result = html(t'<{Heading} title="My Title">Child</{Heading}>')
assert str(result) == '<h1>My Title</h1><div>Child</div>'
```

Note how the component closes with `</{Heading}>` when it contains nested
children, as opposed to the self-closing form in the first example.

Note also that components functions can return `Node` or `Template` values as
they wish. Iterables of nodes and templates are also supported.

## Optional Props

Since this is typical function-argument stuff, you can have optional props
through argument defaults:

```python
def Heading(title: str = "My Title") -> Template:
    return t"<h1>{title}</h1>"

result = html(t"<{Heading} />")
assert str(result) == '<h1>My Title</h1>'
```

## Passsing Another Component as a Prop

Here's a useful pattern: you can pass a component as a "prop" to another
component. This lets the caller (in this case, the `result` line) do the
driving:

```python
def DefaultHeading() -> Template:
    return t"<h1>Default Heading</h1>"

def Body(heading: str) -> Template:
    return t"<body><{heading} /></body>"

result = html(t"<{Body} heading={DefaultHeading} />")
assert str(result) == '<body><h1>Default Heading</h1></body>'
```

## Default Component for Prop

As a variation, let the caller do the driving but make the prop default to a
default component if none was provided:

```python
def DefaultHeading() -> Template:
    return t"<h1>Default Heading</h1>"

def OtherHeading() -> Template:
    return t"<h1>Other Heading</h1>"

def Body(heading: ComponentCallable) -> Template:
    return html(t"<body><{heading} /></body>")

result = html(t"<{Body} heading={OtherHeading}></{Body}>")
assert str(result) == '<body><h1>Other Heading</h1></body>'
```

## Conditional Default

One final variation for passing a component as a prop... move the "default or
passed-in" decision into the template itself:

```python
def DefaultHeading() -> Template:
    return t"<h1>Default Heading</h1>"

def OtherHeading() -> Template:
    return t"<h1>Other Heading</h1>"

def Body(heading: ComponentCallable | None = None) -> Template:
    return t"<body><{heading if heading else DefaultHeading} /></body>"

result = html(t"<{Body} heading={OtherHeading}></{Body}>")
assert str(result) == '<body><h1>Other Heading</h1></body>'
```

## Generators as Components

You can also have components that act as generators. For example, imagine you
have a todo list. There might be a lot of todos, so you want to generate them in
a memory-efficient way:

```python
def Todos() -> Iterable[Template]:
    for todo in ["first", "second", "third"]:
        yield t"<li>{todo}</li>"

result = html(t"<ul><{Todos} /></ul>")
assert str(result) == '<ul><li>first</li><li>second</li><li>third</li></ul>'
```

## Nested Components

Components can be nested just like any other templating or function call:

```python
def Todo(label: str) -> Template:
    return t"<li>{label}</li>"

def TodoList(labels: Iterable[str]) -> Template:
    return t"<ul>{[Todo(label) for label in labels]}</ul>"

title = "My Todos"
labels = ["first", "second", "third"]
result = html(t"<h1>{title}</h1><{TodoList} labels={todos} />")
# <h1>My Todos</h1><ul><li>first</li><li>second</li><li>third</li></ul>
```
