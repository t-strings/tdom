# Why `tdom`?

Great, another template language! Why `tdom` (and for that matter,
[t-strings](https://peps.python.org/pep-0750/))? Briefly:

- Treat templating like software, but in HTML
- Mirror the patterns from JSX for an easy transition back to Python
- Works well in the browser (PyScript, MicroPython)

## Bring fullstack back to Python

In recent years, Python seems to have gotten out of the business of web UIs.
Instead, developers ship JSON to React. However, a growing number of web
developers have pushed back on the React-ification of the web, noting the
benefits of generating HTML on the server.

Why did developers go through all the trouble to shift from server-side
rendering (SSR) to a new language, tooling, and complexity? One reason:
developer experience (DX.)

`tdom` recognizes this and tries to bring comparable development to Python
fullstack.

## Developer-centric web interfaces

Python has great templating languages—why a possibly insurmountable challenge?

When these languages were created, web designers were a different role. They
weren't Python programmers. So they were given a parallel universe (the
"template") that was a little like Python, but not Python. After all, they
weren't really considered part of the software team.

In the frontend/React world, UIs are created by developers, using programming
languages and tooling. For JSX in particular, the dynamic parts of the language
(scope rules, expressions, control flow, etc.) are actually JavaScript. This
differs sharply from Jinja, for example.

## Pythonic templating

Because of this, in the frontend world, it's easier for tooling to help. But in
Python templates, none of the following are straightforward:

- Refactoring, navigation, squiggles, and other IDE features
- Formatting
- Linting
- Type checking
- Testing

`tdom` is aimed at people that want those things, for their web UIs. Python
tooling has matured greatly since our main templating languages were created.
These benefits should apply to the web part.

How does `tdom` achieve this? It uses t-strings, which are part of the Python
language itself. This means the Python parts (stuff inside `{}`) are
automatically known by tooling. This t-string support was straightforward to add
because t-strings are syntax/scope/etc. almost exactly the same as f-strings.
`ruff` and PyCharm able to add basic t-string support quite easily.

Next, the `tdom` way of composition through components is just a Python
callable. You import it, then use it in your template. HTML attributes become
arguments to the callable, which returns a stringable result. This is much
different than magical macros in special files that get jammed into the
namespace.

## HTML-oriented

Of course, a number of recent Python libraries tackle exactly this, in an even
more Pythonic way: by eliminating HTML itself and making Python calls to build
up the UI. This is similar to what React has
[underneath JSX](https://react.dev/reference/react/createElement).

This builder-oriented
[goes back 25 years](https://www.linuxjournal.com/article/2986) in Python. It
has a certain appeal but has never made a dent in the popularity of HTML-based
templating. Some group of fullstack developers want a string of HTML.

That said, there is a hope to build an ecosystem that supports interoperability
between patterns. This leads to a north star for `tdom`.

## Broad ecosystem of quality, interoperable themes and components

Python has outsourced much of its web UI story to React. What's left is split
between different ecosystems and syntax. We badly need our available design and
web development skills to scale across all of Python's web development.

It's a goal of this project to bring some interoperability between all parts of
Python web development.
