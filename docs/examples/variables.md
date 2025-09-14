# Variables

Inserting a variable into a template mimics what you would expect from a Python
f-string.

## Insert Value Into Template

In this case, `name` comes from the immediate scope:

<!-- invisible-code-block: python
from tdom import html
-->

```python
name = "tdom"
result = html(t"<div>Hello {name}</div>")
assert str(result) == '<div>Hello tdom</div>'
```

## Passed-In Prop

Here, `name` is passed into a function:

```python
def hello(name: str) -> Template:
    return html(t"<div>Hello {name}</div>")

result = hello("tdom")
assert str(result) == '<div>Hello tdom</div>'
```

## Unsafe Values

TODO: write this section

`tdom` now builds on top of
[MarkupSafe](https://markupsafe.palletsprojects.com/en/stable/).
