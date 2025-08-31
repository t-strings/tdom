# Context

We'd like an extensible system. In fact, we'd like the extensibility to be extensible, allowing the core to be simple
and basic. We'd also like to avoid "prop-drilling", where basic data such as configuration has to be passed down the component tree.

As such, `tdom` supports calling the `html` function with an optional dict-like `context` argument. For example:

```python
def Header(context):
    label = context["label"]
    return html(t"Hello {label}")


request = {"label": "World"}
result = html(t"<{Header}/>", context=request)
assert "Hello World" == str(result)
```

This `context` is passed down the entire calling tree, including into components whose signature asks for it. It is unopinionated: add-on frameworks can introduce their own things to
go in the context. In fact, frameworks can make the extra `html` argument hidden behind their own conventions.

Because it is per-render, you can write into objects in the context. For example, subcomponents can add stylesheets
that should ultimately go into the `<head>` at final render time.

## Current hooks

This context support currently has only a few places for pluggability.

- Components can ask for the `context` in their arguments (like `children`)

## Middleware

TODO

- A site can override a system component via the registry (see `get_component_value` for the lookup)
- Explain middleware
- Re-implement the decorator methods as getting callables from the container

Switch from a simple dict as the container, to a global svcs registry
and a per-request container. This shows some patterns along the way:

- Just a global registry, close to the basic example, with a dict interface

- A stateful decorator using venusian that has access to the global registry

- Make a svcs container for each "request" and use that instead

- Simplify this by having a pluggable app that manages the svcs part

- A decorator that configures middleware on all components

- A decorator that configures middleware just for its wrapped component

- Stateful middleware, such as a helmet-style per-request

- Lifecycle rendering, to generate a responsive image and update the node later

Note that none of this requires any changes to `tdom` beyond passing down
a container.
