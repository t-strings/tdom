# Expressions

In Python f-strings, the curly brackets can take not just variable names, but
also Python "expressions" inside a t-string's interpolation.

The same is true in `tdom`.

## Simple Arithmetic

Let's use an expression which adds two numbers together:

<!-- invisible-code-block: python
from tdom import html
-->

```python
result = html(t"<div>{1 + 3}</div>")
assert str(result) == '<div>4</div>'
```

## Python Operation

Just like with f-strings, you can use any valid Python expression inside the
curly braces:

```python
result = html(t"<div>{','.join(['a', 'b', 'c'])}</div>")
assert str(result) == '<div>a,b,c</div>'
```

## Call a Function

But it's Python and f-strings-ish, so you can do even more.

For example, call an in-scope function with an argument, which does some work,
and insert the result:

```python
def make_big(s: str) -> str:
    return f"SO VERY BIG: {s.upper()}"

result = html(t"<div>{make_big('hello')}</div>")
assert str(result) == '<div>SO VERY BIG: HELLO</div>'
```
