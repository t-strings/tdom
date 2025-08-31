---
apply: always
---

# Support Python 3.14 t-strings

Let's teach AI Assistant about t-strings, tdom, and components.

- Python 3.14 has a feature called template strings, also referred to as t-strings.

- First, read PEP 750 - Template Strings at https://peps.python.org/pep-0750/

- Template functions, also called t-string functions, are passed a `string.templatelib.Template` object and return a
  string.

- Always return a string that combines the parts.

- These t-strings contain static string part and interpolation parts.

- Use structural pattern matching, as shown in the PEP examples, when analyzing the parts.

- Always use type hints on the function arguments and return values.

