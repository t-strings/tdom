# tdom

A 🤘 rockin' t-string HTML templating system for Python 3.14.

[![PyPI](https://img.shields.io/pypi/v/tdom.svg)](https://pypi.org/project/tdom/)
[![Tests](https://github.com/t-strings/tdom/actions/workflows/ci.yml/badge.svg)](https://github.com/t-strings/tdom/actions/workflows/ci.yml)
[![Test Count](https://t-strings.github.io/tdom/reports/pytest.svg)](https://t-strings.github.io/tdom/reports/pytest.html)
[![Coverage](https://t-strings.github.io/tdom/reports/coverage.svg)](https://t-strings.github.io/tdom/reports/coverage/index.html)
[![Changelog](https://img.shields.io/github/v/release/t-strings/tdom?include_prereleases&label=changelog)](https://github.com/t-strings/tdom/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/t-strings/tdom/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://t-strings.github.io/tdom/)

## Installation

Just run:

```bash
pip install tdom
```

Python 3.14 isn't out yet, but you can use
[Astral's `uv`](https://docs.astral.sh/uv/) to easily try `tdom` in a Python
3.14 environment:

```bash
uv run --with tdom --python 3.14 python
```

## Usage

`tdom` leverages Python 3.14's
[new t-strings feature](https://t-strings.help/introduction.html) to provide a
powerful HTML templating system that feels familiar if you've used JSX, Jinja2,
or Django templates.

T-strings work just like f-strings but use a `t` prefix and
[create `Template` objects](https://docs.python.org/3.14/library/string.templatelib.html#template-strings)
instead of strings.

Once you have a `Template`, you can call this package's `html()` function to
convert it into a tree of `Node` objects that represent your HTML structure.
From there, you can render it to a string, manipulate it programmatically, or
compose it with other templates for maximum flexibility.

### Getting Started

Import the `html` function and start creating templates:

```python
from tdom import html
greeting = html(t"<h1>Hello, World!</h1>")
print(type(greeting))  # <class 'tdom.nodes.Element'>
print(greeting)  # <h1>Hello, World!</h1>
```

### Variable Interpolation

Just like f-strings, you can interpolate (substitute) variables directly into
your templates:

```python
name = "Alice"
age = 30
user_info = html(t"<p>Hello, {name}! You are {age} years old.</p>")
print(user_info)  # <p>Hello, Alice! You are 30 years old.</p>
```

The `html()` function ensures that interpolated values are automatically escaped
to prevent XSS attacks:

```python
user_name = "<script>alert('owned')</script>"
safe_output = html(t"<p>Hello, {user_name}!</p>")
print(safe_output)  # <p>Hello, &lt;script&gt;alert('owned')&lt;/script&gt;!</p>
```

### Attribute Substitution

The `html()` function provides a number of convenient ways to define HTML
attributes.

#### Direct Attribute Values

You can place values directly in attribute positions:

```python
url = "https://example.com"
link = html(t'<a href="{url}">Visit our site</a>')
# <a href="https://example.com">Visit our site</a>
```

You don't _have_ to wrap your attribute values in quotes:

```python
element_id = "my-button"
button = html(t"<button id={element_id}>Click me</button>")
# <button id="my-button">Click me</button>
```

Multiple substitutions in a single attribute are supported too:

```python
first = "Alice"
last = "Smith"
button = html(t'<button data-name="{first} {last}">Click me</button>')
# <button data-name="Alice Smith">Click me</button>
```

Boolean attributes are supported too. Just use a boolean value in the attribute
position:

```python
form_button = html(t"<button disabled={True} hidden={False}>Submit</button>")
# <button disabled>Submit</button>
```

#### The `class` Attribute

The `class` attribute has special handling to make it easy to combine multiple
classes from different sources. The simplest way is to provide a list of class
names:

```python
classes = ["btn", "btn-primary", "active"]
button = html(t'<button class="{classes}">Click me</button>')
# <button class="btn btn-primary active">Click me</button>
```

For flexibility, you can also provide a list of strings, dictionaries, or a mix
of both:

```python
classes = ["btn", "btn-primary", {"active": True}, None, False and "disabled"]
button = html(t'<button class="{classes}">Click me</button>')
# <button class="btn btn-primary active">Click me</button>
```

See the
[`classnames()`](https://github.com/t-strings/tdom/blob/main/tdom/classnames_test.py)
helper function for more information on how class names are combined.

#### The `style` Attribute

In addition to strings, you can also provide a dictionary of CSS properties and
values for the `style` attribute:

```python
# Style attributes from dictionaries
styles = {"color": "red", "font-weight": "bold", "margin": "10px"}
styled = html(t"<p style={styles}>Important text</p>")
# <p style="color: red; font-weight: bold; margin: 10px">Important text</p>
```

#### The `data` and `aria` Attributes

The `data` and `aria` attributes also have special handling to convert
dictionary keys to the appropriate attribute names:

```python
data_attrs = {"user-id": 123, "role": "admin"}
aria_attrs = {"label": "Close dialog", "hidden": True}
element = html(t"<div data={data_attrs} aria={aria_attrs}>Content</div>")
# <div data-user-id="123" data-role="admin" aria-label="Close dialog"
# aria-hidden="true">Content</div>
```

Note that boolean values in `aria` attributes are converted to `"true"` or
`"false"` as per [the ARIA specification](https://www.w3.org/TR/wai-aria-1.2/).

#### Attribute Spreading

It's possible to specify multiple attributes at once by using a dictionary and
spreading it into an element using curly braces:

```python
attrs = {"href": "https://example.com", "target": "_blank"}
link = html(t"<a {attrs}>External link</a>")
# <a href="https://example.com" target="_blank">External link</a>
```

You can also combine spreading with individual attributes:

```python
base_attrs = {"id": "my-link"}
target = "_blank"
link = html(t'<a {base_attrs} target="{target}">Link</a>')
# <a id="my-link" target="_blank">Link</a>
```

Special attributes likes `class` behave as expected when combined with
spreading:

```python
classes = ["btn", {"active": True}]
attrs = {"class": classes, "id": "act_now", "data": {"wow": "such-attr"}}
button = html(t'<button {attrs}>Click me</button>')
# <button class="btn active" id="act_now" data-wow="such-attr">Click me</button>
```

### Conditional Rendering

You can use Python's conditional expressions for dynamic content:

```python
is_logged_in = True
user_content = t"<span>Welcome back!</span>"
guest_content = t"<a href='/login'>Please log in</a>"
header = html(t"<div>{user_content if is_logged_in else guest_content}</div>")
# <div><span>Welcome back!</span></div>
```

Short-circuit evaluation is also supported for conditionally including elements:

```python
show_warning = False
warning = t'<div class="alert">Warning message</div>'
page = html(t"<main>{show_warning and warning}</main>")
# <main></main>
```

### Lists and Iteration

Generate repeated elements using list comprehensions:

```python
fruits = ["Apple", "Banana", "Cherry"]
fruit_list = html(t"<ul>{[t'<li>{fruit}</li>' for fruit in fruits]}</ul>")
# <ul><li>Apple</li><li>Banana</li><li>Cherry</li></ul>
```

### Raw HTML Injection

The `tdom` package provides several ways to include trusted raw HTML content in
your templates. This is useful when you have HTML content that you _know_ is
safe and do not wish to escape.

Under the hood, `tdom` builds on top of the familiar
[MarkupSafe](https://pypi.org/project/MarkupSafe/) library to handle trusted
HTML content. If you've used Flask, Jinja2, or similar libraries, this will feel
very familiar.

The `Markup` class from MarkupSafe is available for use:

```python
from tdom import html, Markup

trusted_html = Markup("<strong>This is safe HTML</strong>")
content = html(t"<div>{trusted_html}</div>")
# <div><strong>This is safe HTML</strong></div>
```

As a convenience, `tdom` also supports a `:safe` format specifier that marks a
string as safe HTML:

```python
trusted_html = "<em>Emphasized text</em>"
page = html(t"<p>Here is some {trusted_html:safe} content.</p>")
# <p>Here is some <em>Emphasized text</em> content.</p>
```

For interoperability with other templating libraries, any object that implements
a `__html__` method will be treated as safe HTML. Many popular libraries
(including MarkupSafe and Django) use this convention:

```python
class SafeWidget:
    def __html__(self):
        return "<button>Custom Widget</button>"

page = html(t"<div>My widget: {SafeWidget()}</div>")
# <div>My widget: <button>Custom Widget</button></div>
```

You can also explicitly mark a string as "unsafe" using the `:unsafe` format
specifier. This forces the string to be escaped, even if it would normally be
treated as safe:

```python
from tdom import html, Markup
trusted_html = Markup("<strong>This is safe HTML</strong>")
page = html(t"<div>{trusted_html:unsafe}</div>")
# <div>&lt;strong&gt;This is safe HTML&lt;/strong&gt;</div>
```

### Template Composition

You can easily combine multiple templates and create reusable components.

Template nesting is straightforward:

```python
content = t"<h1>My Site</h1>"
page = html(t"<div>{content}</div>")
# <div><h1>My Site</h1></div>
```

In the example above, `content` is a `Template` object that gets correctly
parsed and embedded within the outer template. You can also explicitly call
`html()` on nested templates if you prefer:

```python
content = html(t"<h1>My Site</h1>")
page = html(t"<div>{content}</div>")
# <div><h1>My Site</h1></div>
```

The result is the same either way.

#### Component Functions

You can create reusable component functions that generate templates with dynamic
content and attributes. Use these like custom HTML elements in your templates.

The basic form of all component functions is:

```python
from typing import Any, Iterable
from tdom import Node, html

def MyComponent(children: Iterable[Node], **attrs: Any) -> Node:
    return html(t"<div {attrs}>Cool: {children}</div>")
```

To _invoke_ your component within an HTML template, use the special
`<{ComponentName} ... />` syntax:

```python
result = html(t"<{MyComponent} id='comp1'>Hello, Component!</{MyComponent}>")
# <div id="comp1">Cool: Hello, Component!</div>
```

Because attributes are passed as keyword arguments, you can explicitly provide
type hints for better editor support:

```python
from typing import Any
from tdom import Node, html

def Link(*, href: str, text: str, data_value: int, **attrs: Any) -> Node:
    return html(t'<a href="{href}" {attrs}>{text}: {data_value}</a>')

result = html(t'<{Link} href="https://example.com" text="Example" data-value={42} target="_blank" />')
# <a href="https://example.com" target="_blank">Example: 42</a>
```

Note that attributes with hyphens (like `data-value`) are converted to
underscores (`data_value`) in the function signature.

Component functions build children and can return _any_ type of value; the
returned value will be treated exactly as if it were placed directly in a child
position in the template.

Among other things, this means you can return a `Template` directly from a
component function:

```python
def Greeting(name: str) -> Template:
    return t"<h1>Hello, {name}!</h1>"

result = html(t"<{Greeting} name='Alice' />")
# <h1>Hello, Alice!</h1>
```

You may also return an iterable:

```python
from typing import Iterable

def Items() -> Iterable[Template]:
    return [t"<li>first</li>", t"<li>second</li>"]

result = html(t"<ul><{Items} /></ul>")
# <ul><li>first</li><li>second</li></ul>
```

If you prefer, you can use **explicit fragment syntax** to wrap multiple
elements in a `Fragment`:

```python
def Items() -> Node:
    return html(t'<><li>first</li><li>second</li></>')

result = html(t'<ul><{Items} /></ul>')
# <ul><li>first</li><li>second</li></ul>
```

This is not required, but it can make your intent clearer.

#### Class-based components

Component functions are great for simple use cases, but for more complex
components you may want to use a class-based approach. Remember that the
component invocation syntax (`<{ComponentName} ... />`) works with any callable.
That includes the `__init__` method or `__call__` method of a class.

One particularly useful pattern is to build class-based components with
dataclasses:

```python
from dataclasses import dataclass, field
from typing import Any, Iterable
from tdom import Node, html

@dataclass
class Card:
    children: Iterable[Node]
    title: str
    subtitle: str | None = None

    def __call__(self) -> Node:
        return html(t"""
            <div class='card'>
                <h2>{self.title}</h2>
                {self.subtitle and t'<h3>{self.subtitle}</h3>'}
                <div class="content">{self.children}</div>
            </div>
        """)

result = html(t"<{Card} title='My Card' subtitle='A subtitle'><p>Card content</p></{Card}>")
# <div class='card'>
#     <h2>My Card</h2>
#     <h3>A subtitle</h3>
#     <div class="content"><p>Card content</p></div>
# </div>
```

This approach allows you to encapsulate component logic and state within a
class, making it easier to manage complex components.

As a note, `children` are optional in component signatures. If a component
requests children, it will receive them if provided. If no children are
provided, the value of children is an empty tuple. If the component does _not_
ask for children, but they are provided, then they are silently ignored.

#### SVG Support

TODO: say more about SVG support

#### Context

TODO: implement context feature

### The `tdom` Module

#### Working with `Node` Objects

TODO: say more about working with them directly

#### The `classnames()` Helper

TODO: say more about it

#### Utilities

TODO: say more about them

## Supporters

TODO: add supporters
