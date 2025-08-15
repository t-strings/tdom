# Context and Containers

We'd like an extensible system. In fact, we'd like the extensibility to be extensible, allowing the core to be simple
and basic.

As such, `tdom` supports calling the `html` function with an optional dict-like `container` argument. For example:

```python
def Header(container):
    label = container["label"]
    return html(t"Hello {label}")
request_container = {"label": "World"}
result = html(t"<{Header}/>", container=request_container)
assert "Hello World" == str(result)
```

This `container` is expected to be a per-render object. It is passed down the entire calling tree, including passed 
into components whose signature asks for it. It is unopinionated: add-on frameworks can introduce their own things to 
go in the container. In fact, frameworks can make the extra `html` argument hidden behind their own conventions.

Because it is per-request, you can write into objects in the container. For example, subcomponents can add stylesheets 
that should ultimately go into the `<head>` at final render time.

Look in `tests/test_basic_container.py` for usages.

## Using `svcs` as a registry and container

As the tests show, one can ignore the `container` argument altogether or use a plain `dict`.

For more advanced systems with a better DX, the container can come from [svcs](https://svcs.hynek.me/en/stable/). To 
see this in action, look in `test_svcs_registry.py` and `test_svcs_container.py`.

## Current hooks

This container support currently has only a few places for pluggability.

- Components can ask for the `container` in their arguments (like `children`)

TODO
- A site can override a system component via the registry (see `get_component_value` for the lookup)
- Explain decorator support
- Explain middleware