# Looping

It's common in templating to format a list of items, for example, a `<ul>` list.
Many Python template languages invent a Python-like grammar to do `for` loops
and the like.

## Simple Looping

You know what's more Python-like? Python.

f-strings can do looping in a Python expression using list comprehensions and so
can `tdom`:

<!-- invisible-code-block: python
from tdom import html
-->

```python
message = "Hello"
names = ["World", "Universe"]
result = html(
    t"""
        <ul title="{message}">
            {[t'<li>{name}</li>' for name in names]}
        </ul>
    """
)
assert str(result) == """
        <ul title="Hello">
            <li>World</li><li>Universe</li>
        </ul>
    """
```

## Rendered Looping

You could also move the generation of the items out of the "parent" template,
then use that `Node` result in the next template:

```python
message = "Hello"
names = ["World", "Universe"]
items = [html(t"<li>{label}</li>") for label in names]
result = html(t"<ul title={message}>{items}</ul>")
assert str(result) == '<ul title="Hello"><li>World</li><li>Universe</li></ul>'
```
