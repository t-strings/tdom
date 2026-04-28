from contextvars import ContextVar, Token


class ContextVarSetter:
    """
    Context manager for working with many context vars (instead of only 1).

    This is meant to be created, used immediately and then discarded.

    This allows for dynamically specifying a tuple of var / value pairs that
    another part of the program can use to wrap some called code without knowing
    anything about either.
    """

    context_values: tuple[tuple[ContextVar, object], ...]  # Cvar / value pair.
    tokens: tuple[Token, ...]

    def __init__(self, context_values=()):
        self.context_values = context_values
        self.tokens = ()

    def __enter__(self):
        """Set every given context var to its paired value."""
        self.tokens = tuple(var.set(val) for var, val in self.context_values)

    def __exit__(self, exc_type, exc_value, traceback):
        """Reset every given context var."""
        for idx, var_value in enumerate(self.context_values):
            var_value[0].reset(self.tokens[idx])
