# Expressions

In Python f-strings, the curly brackets can take not just variable names, but also Python "expressions".

Same is true in `tdom`.

## Python Operation

Let's use an expression which adds two numbers together:

```{literalinclude} ../../examples/expressions/python_operation/__init__.py
---
start-at: def main
---
```

## Simple Arithmetic

Let's use an expression which adds two numbers together:

```{literalinclude} ../../examples/expressions/simple_arithmetic/__init__.py
---
start-at: def main
---
```

## Call a Function

But it's Python and f-strings-ish, so you can do even more.
For example, call an in-scope function with an argument, which does some work, and insert the result:

```{literalinclude} ../../examples/expressions/call_function/__init__.py
---
start-at: def
---
```
