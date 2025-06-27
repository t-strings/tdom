"""Custom processing for components.

This could all ship outside of tdom. These decorators can provide:

- Different calling semantics, e.g. adding "container" or DI
- Middleware with lifecycles
"""
import functools
from inspect import signature

from venusian import Scanner, attach

def injectable(wrapped):
    _scanner: Scanner | None = None
    param_names = [param.name for param in signature(wrapped).parameters.values()]

    @functools.wraps(wrapped)
    def _inject(*args, **kwargs):
        """Wrap the callable with a factory that can supply the registry."""
        if _scanner is None:
            return wrapped(*args, **kwargs)
        # Let's inject the registry if it is asked for
        _kwargs = kwargs.copy()
        if "registry" in param_names:
            registry = getattr(_scanner, "registry")
            _kwargs["registry"] = registry
        return wrapped(*args, **_kwargs)

    def callback(scanner, name, ob):
        """This is called by venusian at scan time."""
        nonlocal _scanner
        _scanner = scanner

    attach(_inject, callback)
    return _inject
