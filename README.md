# tdom - WIP

A 🔥 t-string (aka PEP 750) HTML templating system for upcoming Python 3.14 for
both server-side rendering and frontend.

[![PyPI](https://img.shields.io/pypi/v/tdom.svg)](https://pypi.org/project/tdom/)
[![Tests](https://github.com/t-strings/tdom/actions/workflows/pytest.yml/badge.svg)](https://github.com/t-strings/tdom/actions/workflows/pytest.yml)
[![Changelog](https://img.shields.io/github/v/release/t-strings/tdom?include_prereleases&label=changelog)](https://github.com/t-strings/tdom/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/t-strings/tdom/blob/main/LICENSE)

[Live demo](https://t-strings.help/playground.html)

## Installation

`tdom` uses Python 3.14. At the time of this writing, Python 3.14.0rc2 was the
latest version. You can get this from
[python.org](https://www.python.org/download/pre-releases/) or use an installer
such as `uv`.

```shell
$ pip install tdom
```

## MicroPython

This project intends to provide good support for MicroPython. It doesn't yet
support t-strings directly, but Koudai has a
[MicroPython fork](https://github.com/koxudaxi/micropython/tree/feature/pep750-template-strings)
to build the `webassembly` variant. As a convenience, we have checked in the two
build artifacts in this repo, under `static`.

## tdom development setup

Ths project uses `uv` for environment management. Clone this repo have `uv`
create a virtual environment:

```shell
$ git clone https://github.com/t-strings/tdom.git
$ cd tdom
$ uv sync
```

The repo has its own `.python-version` but you can override it if you need a
different Python version.

## Testing

The `tdom` project has a decent set of tests. The pytest configuration is in
`pyproject.toml` as well as the GitHub Actions workflows in `.github/workflows`.
To run them:

```shell
$ uv run pytest
```

Some useful notes about the testing:

- The `examples` are used for development and documentation but each example is
  also part of the test suite.
- `tdom.fixtures` has Playwright setup fixtures to serve assets from disk. These
  work by registering a network interceptor for `http://localhost:8000`.
- Thus, we also have tests based on browser execution, using a local in-repo
  version of MicroPython.
- A custom `integration` marker is defined and used in `pyproject.toml`. This
  mark is used on Playwright tests to allow running just the fast tests.

## Building docs

```shell
$ uv run sphinx-build docs docs/_build
```

## Examples web app

The file at `index.html` provides a static web page that loads all the examples
into a web page. You can execute them or edit and re-execute. This web app and
the examples serve several uses:

- Public in-browser playground for `tdom` use cases
- Smooth local development experience for `tdom` itself to target MicroPython
  first
- Pre-configured, local-only, serverless `pytest-playwright` web app to ensure
  `tdom` works with the examples, in MicroPython

## Features + Quick walk through

The current _SSR_ implementation offers three major features that can be split
into these categories:

- **[attributes](#attributes)**, meant as HTML/SVG nodes attributes
- **[content](content)**, meant as HTML/SVG elements or fragments possibilities
- **[components](components)**, meant as classes or functions that return some
  _content_ after being instantiated/invoked

### Attributes

An element attribute is nothing more than a _name/value_ pair definition, where
the `name` must be unique, and it might have a special meaning, accordingly with
the element where such an attribute is defined.

```html
<!-- HTML -->
<div class="class-attribute">
  <!-- some content -->
</div>
<textarea placeholder="Your comment"></textarea>

<!-- SVG -->
<rect width="200" height="100" rx="20" ry="20" fill="blue" />
```

Thanks to `t` strings, attributes in here can be _dynamic_ or even _mixed_,
example:

```html
<div class="{''.join(['special', 'container'])}">
  <!-- some content -->
</div>
<textarea placeholder="{placeholder}"></textarea>

<rect width="{width}" height="{height}" rx="20" ry="20" fill="{color}" />
```

**Note**

- it doesn't matter if dynamic attributes have single or double quotes around,
  the logic is smart enough to understand and ultimately sanitize those quotes
  around, even if omitted
- it doesn't matter if the value is an integer, float, or something else, once
  stringified the output will use `str(value)` and it will safely `escape` those
  values automatically
- attributes **must** be a single value, when dynamic, so that the following
  would break:

```html
<!-- ⚠️ this is not possible -->
<div class="a {runtime} b"></div>


<!-- 👍 this works perfectly fine -->
<div class={f"a {runtime} b"}></div>
<div class={callback}></div>
<div class={some_class(runtime)}></div>
```

#### Special Attributes

Some HTML attributes might not need a value to be significant, and for these
special cases a **boolean** hint would be enough to see it rendered or not. The
[hidden](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/hidden)
attribute is one of those special cases:

```html
<div hidden="{condition}">
  <!-- some content -->
</div>
```

When that `condition` is `True`, `<div hidden>` will be produced once the
template will get stringified, while if `False` it won't be part of the output
at all, it's just `<div>`.

The **aria** attribute is
[also special](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes)
because it allows automatically creating all related attributes with ease,
without needing to repeat `aria-` prefix all over the place:

```html
<div aria={{"role": "button", "describedby": uid}}>
  <!-- some content -->
</div>

<!-- will result into -->
<div role="button" aria-describedby="unique-id">
  <!-- some content -->
</div>
```

Similarly, the **data** attribute helps add
[dataset](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dataset)
attributes to any node, without needing to repeat the `data-` prefix.

```html
<div data={{"a": 1, "b": 2, "c": 3}}>
  <!-- some content -->
</div>

<!-- will result into -->
<div data-a="1" data-b="2" data-c="3">
  <!-- some content -->
</div>
```

Last, but not least, `@events` are currently specially handled as well, such as
`@click`, `@pointerover` and every other standard _event_ will be translated
into a specialized listener that will either work or silently do nothing unless
instrumented/orchestrated explicitly.

```html
<button @click="{my_click_handler}">click me</button>

<!-- will result into -->
<button onclick="self.python_listeners?.[0](event)">click me</button>
```

Currently experimental, we've already managed to bring real Python listeners to
the browser via `dill` module and [PyScript](https://pyscript.net/) ability to
bootstrap [pyodide](https://pyodide.org/en/stable/) on the front end, but any
custom logic able to map listeners to actual actions on the page could work
similarly, if not better.

### Content

Runtime content can be placed almost anywhere. It could represent a string,
number, node returned by `html` or `svg` utility, or a callback that will be
invoked to return any of these values or, ultimately, a `list` or a `tuple` that
contains any previously mentioned value, or a component.

```html
<div>
  Some {'text'}. Some {lambda_or_function}
  <ul>
    {[ html(t'
    <li>{'a'}</li>
    '), html(t'
    <li>b</li>
    '), html(t'
    <li>c {sep} d</li>
    '), ]}
  </ul>
  <{MyComponent} a='1' b={2} />
</div>
```

### Components

Differently from functions found as interpolation value within the content, a
component is a function, or a class, that will be invoked, or instantiated with
two arguments, `props` and `children`, but it requires to be present right after
an opening `<` char, otherwise it won't receive any value:

```python
def MyComponent(a:int, b:int, children:list):
  # a == 1 and b == 2
  # children == [<p />, <p />]
  return html(t'<div data={props}>{children}</div>')

print(
  str(
    html(t'''
      <{MyComponent} a="1" b={2}>
        <p>first element {'child'}</p>
        <p c={3}>second element child</p>
      </>
    ''')
  )
)
```

The output that will result is:

```html
<div data-a="1" data-b="2">
  <p>first element 'child'</p>
  <p c="3">second element child</p>
</div>
```

where all `children` will be passed along already resolved and all `props` will
contain every "_attribute_" defined at the component level: _props_ is just a
special _dictionary_ that allows both `props.x` and `props['x']` ways to read
its own values.

### A note about special syntax

In these examples it is possible to note _self-closing tags_, such as `<div />`
or others, but also a special _closing-tag_ such as `</>` or `<//>` (these are
the same).

The `@` attribute for events is also not standard, but it helps explicitly
distinguish between what could be an actual _JS_ content for a real `onclick`,
as opposite of being something "_magic_" that needs to be orchestrated @ the
_Python_ level.

## Supporters

`tdom` is an independent open source project, started by Andrea Giammarchi. His
time, though, has generously been supported by his work at
[Anaconda](https://www.anaconda.com). Thank you Anaconda for your continued
support of this project.
