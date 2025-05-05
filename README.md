# tdom - WIP

PEP 750 based t-strings for both server-side rendering and frontend.

[Live demo](https://webreflection.github.io/tdom/src/)

## Installation

We don't yet have a package published on PyPI, so follow the instructions below. Once template strings are merged into
a Python 3.14 beta, we'll publish a package, and you can install from `pip`, `uv`, etc.

## Python 3.14 setup

*Note: These instructions point at an old version of template strings. We need some Pyodide work to start using the new
API. So we'll use the old API for the CPython by cloning an old commit.*

First, clone CPython `main` then build it in some directory.

```shell
$ cd /tmp
$ git clone https://github.com/python/cpython.git
$ cd cpython
$ ./configure  # Follow https://devguide.python.org
$ make
```

On macOS/Windows, this will produce a file `python.exe` (on Linux, `python`) which you will use as your Python executable.

## tdom development setup

Let's get `tdom` setup for development. Clone this repo and make a virtual environment there, using the just-built
CPython:

```shell
$ git clone https://github.com/WebReflection/tdom.git
$ cd tdom
$ /tmp/cpython/python.exe -m venv .venv  # Use your path to Python build
$ .venv/bin/pip install --upgrade pip
```

Let's use `uv` from now on. Install it
using [one of the uv install method](https://docs.astral.sh/uv/getting-started/installation/). Specifically,
we will use `uv run pytest`, if you are using the command line as your test UI.

```shell
$ uv run pytest
```

And that's it!

If you are using an IDE with testing support (PyCharm, VS Code) and it doesn't have `uv run` support, you'll need
another step. Whenever you change dependencies, run `uv sync`, since the IDE is likely running `pytest` directly.

## Features + Quick walk through

The current *SSR* implementation offers 3 major features that can be split into these categories:

  * **[attributes](#attributes)**, meant as HTML/SVG nodes attributes
  * **[content](content)**, meant as HTML/SVG elements or fragments possibilities
  * **[components](components)**, meant as classes or functions that return some *content* after being instantiated/invoked


### Attributes

An element attribute is nothing more than a *name/value* pair definition, where the `name` must be unique and it might have a special meaning, accordingly with the element where such attribute is defined.

```html
<!-- HTML -->
<div class="class-attribute">
  <!-- some content -->
</div>
<textarea placeholder="Your comment">
</textarea>

<!-- SVG -->
<rect width="200" height="100" rx="20" ry="20" fill="blue" />
```

Thanks to `t` strings, attributes in here can be *dynamic* or even *mixed*, example:

```html
<div class="{''.join(['special', 'container'])}">
  <!-- some content -->
</div>
<textarea placeholder={placeholder}>
</textarea>

<rect width={width} height={height} rx="20" ry="20" fill='{color}' />
```

**Note**

  * it doesn't matter if dynamic attributes have single or double quotes around, the logic is smart enough to understand and ultimately sanitize those quotes around, even if omitted
  * it doesn't matter if the value is an integer, float, or something else, once stringified the output will use `str(value)` and it will safely `escape` those values automatically
  * attributes **must** be a single value, when dynamic, so that the following would break:

```html
<!-- ⚠️ this is not possible -->
<div class="a {runtime} b"></div>


<!-- 👍 this works perfectly fine -->
<div class={f"a {runtime} b"}></div>
<div class={callback}></div>
<div class={some_class(runtime)}></div>
```

#### Special Attributes

Some HTML attribute might not need a value to be significant and for these special cases a **boolean** hint would be enough to see it rendered or not. The [hidden](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/hidden) attribute is one of those special cases:

```html
<div hidden={condition}>
  <!-- some content -->
</div>
```

When that `condition` is `True`, `<div hidden>` will be produced once the template will get stringified, while if `False` it won't be part of the output at all, it's just `<div>`.

The **aria** attribute is [also special](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes) because it allows to automatically create all related attributes with ease, without needing to repeat `aria-` prefix all over the place:

```html
<div aria={{"role": "button", "describedby": uid}}>
  <!-- some content -->
</div>

<!-- will result into -->
<div role="button" aria-describedby="unique-id">
  <!-- some content -->
</div>
```

Similarly, the **data** attribute helps adding [dataset](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dataset) attributes to any node, without needing to repeat the `data-` prefix.

```html
<div data={{"a": 1, "b": 2, "c": 3}}>
  <!-- some content -->
</div>

<!-- will result into -->
<div data-a="1" data-b="2" data-c="3">
  <!-- some content -->
</div>
```

Last, but not least, `@events` are currently specially handled as well, such as `@click`, `@pointerover` and every other standard *event* will be translated into a specialized listener that will either work or silently do nothing unless instrumented/orchestrated explicitly.

```html
<button @click={my_click_handler}>
  click me
</button>

<!-- will result into -->
<button onclick="self.python_listeners?.[0](event)">
  click me
</button>
```

Currently experimental, we've already managed to bring real Python listeners to the browser via `dill` module and [PyScript](https://pyscript.net/) ability to bootstrap [pyodide](https://pyodide.org/en/stable/) on the front end, but any custom logic able to map listeners to actual actions on the page could work similarly, if not better.


### Content

Runtime content can be placed almost anywhere and it could represent a string, number, node returned by `html` or `svg` utility or a callback that will be invoked to return any of these values or, ultimately, a `list` or a `tuple` that contains any previously mentioned value, or a component.

```html
<div>
  Some {'text'}.
  Some {lambda_or_function}
  <ul>
    {[
      html(t'<li>{'a'}</li>'),
      html(t'<li>b</li>'),
      html(t'<li>c {sep} d</li>'),
    ]}
  </ul>
  <{MyComponent} a='1' b={2} />
</div>
```


### Components

Differently from functions found as interpolation value within the content, a component is a function, or a class, that will be invoked, or instiated with 2 arguments, `props` and `children`, but it requires to be present right after an opening `<` char, otherwise it won't receive any value:

```python
def MyComponent(props, children):
  # props['a'] == 1 and props.b == 2
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

where all `children` will be passed along already resolved and all `props` will contain every "*attribute*" defined at the component level: *props* is just a special *dictionary* that allows both `props.x` and `props['x']` ways to read its own values.


### A note about special syntax

In these examples it is possible to note *self-closing tags*, such as `<div />` or others, but also a special *closing-tag* such as `</>` or `<//>` (these are the same).

The `@` attribute for events is also not standard, but it helps explicitly distinguish between what could be an actual *JS* content for a real `onclick`, as opposite of being something "*magic*" that needs to be orchestrated @ the *Python* level.

### Building docs

```shell
$ uv run sphinx-build docs docs/_build
```