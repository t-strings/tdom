"""Custom processing for components.

This could all ship outside of tdom. These decorators can provide:

- Different calling semantics, e.g. adding "container" or DI
- Middleware with lifecycles
"""
import functools
from inspect import signature
from typing import Sequence, Callable

from venusian import Scanner, attach

def injectable(after: Sequence[Callable] = tuple()):
    _scanner: Scanner | None = None
    def decorator_injectable(wrapped):
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
            result = wrapped(*args, **_kwargs)
            for middleware in after:
                result = middleware(result)
            return result

    def callback(scanner, name, ob):
        """This is called by venusian at scan time."""
        nonlocal _scanner
        _scanner = scanner

    attach(decorator_injectable, callback)

    return decorator_injectable