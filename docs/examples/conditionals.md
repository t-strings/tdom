# Conditionals

It's a common pattern in templating: return one chunk of HTML most of the time,
but under certain conditions, return a different chunk.

Thus, conditionals are a common part of templating.

They're also a common part of Python f-strings, because...well, Python has
conditionals. Here's a simple example using a Python "ternary":

```python
message = "Say Howdy"
not_message = "So Sad"
show_message = True
result = html(
  t"""
    <h1>Show?</h1>
    {message if show_message else not_message}
  """
)
# <h1>Show?</h1>Say Howdy
```
