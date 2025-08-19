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
see this in action, look in `test_svcs_registry.py` and `test_svcs_container.py`. Or from FastAPI's registry.

None of these would ship in `tdom`, but `tdom` would provide an opportunity to pass it in.

## Current hooks

This container support currently has only a few places for pluggability.

- Components can ask for the `container` in their arguments (like `children`)

### Decorators

- Uses Venusian for delayed initialization
- Decorator args to affect registration
- Designed to be subclassable for "semantic" registrations
- But also, to change plug points in the decorator calling cycle
  - Override collecting kwargs
  - Override calling the target
  - Override applying middleware
  - Later these could all come from the container, which is even easier/more flexible than having to override
- This implementation shows passing in middleware to affect the output
- Access to the registry and then container
- Use of optional "for_" to allow replaceability

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