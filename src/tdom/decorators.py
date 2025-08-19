"""Custom processing for components.

This could all ship outside of tdom. These decorators can provide:

- Different calling semantics, e.g. adding "container" or DI
- Middleware with lifecycles
"""

from dataclasses import is_dataclass
from inspect import signature
from typing import Callable, Optional, Sequence

from svcs import Registry
from venusian import Scanner, attach


class injectable:
    def __init__(
        self,
        after: Sequence[Callable] | None = None,
        for_: Optional[Callable[..., object]] = None,
    ):
        self.after = after
        self.for_ = for_
        self.registry: Registry | None = None
        self.param_names: list[str] = []

    def venusian_callback(self, scanner: Scanner, name: str, target):
        """Custom decorators subclass/override this to affect registration."""
        self.registry = getattr(scanner, "registry")

        if self.for_ is not None:
            # The for_ argument (for now) must be a dataclass
            if not is_dataclass(self.for_):
                msg = f"{name} is not a dataclass"
                raise ValueError(msg)

        # Most common case: no for_
        if self.for_ is None:
            # If using for_, the target must be a dataclass
            if is_dataclass(target):
                # Let's register this as itself
                self.registry.register_factory(target, target)
            else:
                # This is a function, do nothing
                pass
        else:
            # for_ is a dataclass, the target should be too
            if not is_dataclass(target):
                msg = f"{target.__name__} is not a dataclass"
                raise ValueError(msg)
            else:
                # Now register the target "for" the self.for_
                self.registry.register_factory(self.for_, target)

        # Let's sniff the target signature only once, instead of every call.
        self.param_names = [
            param.name for param in signature(target).parameters.values()
        ]

    def get_target(self, container, target):
        """Allow component replacement by override from the container."""
        if not is_dataclass(target):
            return target
        actual_target = container.get(target)
        return actual_target

    def make_args(self, these_kwargs):
        _kwargs = these_kwargs.copy()

        # Let's inject the registry only if it is asked for
        if "registry" in self.param_names:
            _kwargs["registry"] = self.registry

        return _kwargs

    def call_target(self, target, **these_kwargs):
        """Customize the calling of a target."""
        result = target(**these_kwargs)
        return result

    def __call__(self, wrapped):
        def _wrapped(*args, **kwargs):
            container = kwargs.get("container")
            _kwargs = self.make_args(kwargs)
            target = self.get_target(container, wrapped)
            result = self.call_target(target, **_kwargs)

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

        return wrapped
