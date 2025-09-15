import sys
import typing as t
from dataclasses import dataclass
from functools import lru_cache


@dataclass(slots=True, frozen=True)
class CallableInfo:
    """Information about a callable necessary for `tdom` to safely invoke it."""

    id: int
    """The unique identifier of the callable (from id())."""

    named_args: frozenset[str]
    """The names of the callable's named arguments."""

    required_named_args: frozenset[str]
    """The names of the callable's required named arguments."""

    requires_positional: bool
    """Whether the callable requires positional-only argument values."""

    kwargs: bool
    """Whether the callable accepts **kwargs."""

    @classmethod
    def from_callable(cls, c: t.Callable) -> t.Self:
        """Create a CallableInfo from a callable."""
        import inspect

        sig = inspect.signature(c)
        named_args = []
        required_named_args = []
        requires_positional = False
        kwargs = False

        for param in sig.parameters.values():
            match param.kind:
                case inspect.Parameter.POSITIONAL_ONLY:
                    if param.default is param.empty:
                        requires_positional = True
                case inspect.Parameter.POSITIONAL_OR_KEYWORD:
                    named_args.append(param.name)
                    if param.default is param.empty:
                        required_named_args.append(param.name)
                case inspect.Parameter.VAR_POSITIONAL:
                    # Does this necessarily mean it requires positional args?
                    # Answer: No, but we have no way of knowing how many
                    # positional args it *might* require, so we have to assume
                    # it does.
                    requires_positional = True
                case inspect.Parameter.KEYWORD_ONLY:
                    named_args.append(param.name)
                    if param.default is param.empty:
                        required_named_args.append(param.name)
                case inspect.Parameter.VAR_KEYWORD:
                    kwargs = True

        return cls(
            id=id(c),
            named_args=frozenset(named_args),
            required_named_args=frozenset(required_named_args),
            requires_positional=requires_positional,
            kwargs=kwargs,
        )

    @property
    def supports_zero_args(self) -> bool:
        """Whether the callable can be called with zero arguments."""
        return not self.requires_positional and not self.required_named_args


@lru_cache(maxsize=0 if "pytest" in sys.modules else 512)
def get_callable_info(c: t.Callable) -> CallableInfo:
    """Get the CallableInfo for a callable, caching the result."""
    return CallableInfo.from_callable(c)
