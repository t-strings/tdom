# Variables

Inserting a variable into a template mimics what you would expect from a Python f-string.

## Insert Value Into Template

In this case, the template is in a function, and `name` comes from that scope:

```{literalinclude} ../../examples/variables/insert_value/__init__.py
---
start-at: def main
---
```

## Value From Import

In this third case, `name` symbol is imported from another module:

```{literalinclude} ../../examples/variables/value_from_import/__init__.py
---
start-at: def Hello
---
```

## Passed-In Prop

Of course, the function could get the symbol as an argument.
This style is known as "props":

```{literalinclude} ../../examples/variables/passed_in_prop/__init__.py
---
start-at: def Hello
---
```

## Default Value

The function (i.e. the "component") could make passing the argument optional by providing a default:

```{literalinclude} ../../examples/variables/default_value/__init__.py
---
start-at: def Hello
---
```
## Unsafe Values

Sometimes you get content from an untrusted source, and you need to escape it. That's usually a job 
for [MarkupSafe](https://markupsafe.palletsprojects.com/en/stable/). But `tdom` targets MicroPython 
and wants to minimize dependencies, so it provides a small `unsafe` utility. Just use it 
to wrap your values:

```{literalinclude} ../../examples/variables/unsafe/__init__.py
---
start-at: def main
---
```

