"""Custom processing for components.

This could all ship outside of tdom. These decorators can provide:

- Different calling semantics, e.g. adding "container" or DI
- Middleware with lifecycles
"""

import functools
from inspect import signature
from typing import Callable, Sequence

from svcs import Registry
from venusian import Scanner, attach


class injectable:
    def __init__(self, after: Sequence[Callable] | None = None):
        self.after = after
        self.registry: Registry | None = None
        self.param_names: list[str] = []

    def venusian_callback(self, scanner: Scanner, name: str, ob):
        """Custom decorators subclass/override this to affect registration."""
        # Let's sniff the target signature only once, instead of every call.
        self.param_names = [param.name for param in signature(ob).parameters.values()]

        self.registry = getattr(scanner, "registry")

    def make_args(self, these_kwargs):
        _kwargs = these_kwargs.copy()

        # Let's inject the registry only if it is asked for
        if "registry" in self.param_names:
            _kwargs["registry"] = self.registry

        return _kwargs

    def get_target(self, target, **these_kwargs):
        """Allow component replacement by override from the container."""
        container = these_kwargs.get("container")
        result = target(**these_kwargs)
        return result

    def call_target(self, target, **these_kwargs):
        """Customize the calling of a target."""
        result = target(**these_kwargs)
        return result

    def __call__(self, wrapped):
        @functools.wraps(wrapped)
        def _wrapped(*args, **kwargs):
            _kwargs = self.make_args(kwargs)
            result = self.call_target(wrapped, **_kwargs)

            # If "after" was passed in the decorator, apply the middleware
            # callables to the result
            if self.after:
                for middleware in self.after:
                    result = middleware(result)

            return result

        def _venusian_callback(scanner: Scanner, name: str, ob):
            """Basically a lambda."""
            self.venusian_callback(scanner, name, ob)

        attach(_wrapped, _venusian_callback)

        return _wrapped
