import typing as t

from .callables import get_callable_info


def callable_zero_args() -> None:
    """Test callable that takes zero arguments."""
    pass


def test_zero_args() -> None:
    """Test that a callable that takes zero arguments is detected."""
    info = get_callable_info(callable_zero_args)
    assert info.id == id(callable_zero_args)
    assert info.named_args == frozenset()
    assert info.required_named_args == frozenset()
    assert not info.requires_positional
    assert not info.kwargs
    assert info.supports_zero_args


def callable_positional(a: int, b: str) -> None:
    """Test callable that takes positional arguments."""
    pass


def test_positional() -> None:
    """Test that a callable that takes positional arguments is detected."""
    info = get_callable_info(callable_positional)
    assert info.id == id(callable_positional)
    assert info.named_args == frozenset(["a", "b"])
    assert info.required_named_args == frozenset(["a", "b"])
    assert not info.requires_positional
    assert not info.kwargs
    assert not info.supports_zero_args


def callable_positional_only(a: int, /, b: str) -> None:
    """Test callable that takes positional-only arguments."""
    pass


def test_positional_only() -> None:
    """Test that a callable that takes positional-only arguments is detected."""
    info = get_callable_info(callable_positional_only)
    assert info.id == id(callable_positional_only)
    assert info.named_args == frozenset(["b"])
    assert info.required_named_args == frozenset(["b"])
    assert info.requires_positional
    assert not info.kwargs
    assert not info.supports_zero_args


def callable_positional_only_default(a: int = 1, /, b: str = "b") -> None:
    """Test callable that takes positional-only arguments with defaults."""
    pass


def test_positional_only_default() -> None:
    """Test that a callable that takes positional-only arguments with defaults is detected."""
    info = get_callable_info(callable_positional_only_default)
    assert info.id == id(callable_positional_only_default)
    assert info.named_args == frozenset(["b"])
    assert info.required_named_args == frozenset()
    assert not info.requires_positional
    assert not info.kwargs
    assert info.supports_zero_args


def callable_kwargs(**kwargs: t.Any) -> None:
    """Test callable that takes **kwargs."""
    pass


def test_kwargs() -> None:
    """Test that a callable that takes **kwargs is detected."""
    info = get_callable_info(callable_kwargs)
    assert info.id == id(callable_kwargs)
    assert info.named_args == frozenset()
    assert info.required_named_args == frozenset()
    assert not info.requires_positional
    assert info.kwargs
    assert info.supports_zero_args


def callable_mixed(a: int, /, b: str, *, c: float = 1.0, **kwargs: t.Any) -> None:
    """Test callable that takes a mix of argument types."""
    pass


def test_mixed() -> None:
    """Test that a callable that takes a mix of argument types is detected."""
    info = get_callable_info(callable_mixed)
    assert info.id == id(callable_mixed)
    assert info.named_args == frozenset(["b", "c"])
    assert info.required_named_args == frozenset(["b"])
    assert info.requires_positional
    assert info.kwargs
    assert not info.supports_zero_args


def callable_positional_with_defaults(a: int = 1, b: str = "b", /) -> None:
    """Test callable that takes positional arguments with defaults."""
    pass


def test_positional_with_defaults() -> None:
    """Test that a callable that takes positional arguments with defaults is detected."""
    info = get_callable_info(callable_positional_with_defaults)
    assert info.id == id(callable_positional_with_defaults)
    assert info.named_args == frozenset()
    assert info.required_named_args == frozenset()
    assert not info.requires_positional
    assert not info.kwargs
    assert info.supports_zero_args


def callable_keyword_only(*, a: int, b: str = "b") -> None:
    """Test callable that takes keyword-only arguments."""
    pass


def test_keyword_only() -> None:
    """Test that a callable that takes keyword-only arguments is detected."""
    info = get_callable_info(callable_keyword_only)
    assert info.id == id(callable_keyword_only)
    assert info.named_args == frozenset(["a", "b"])
    assert info.required_named_args == frozenset(["a"])
    assert not info.requires_positional
    assert not info.kwargs
    assert not info.supports_zero_args


def callable_var_positional(*args: t.Any) -> None:
    """Test callable that takes *args."""
    pass


def test_var_positional() -> None:
    """Test that a callable that takes *args is detected."""
    info = get_callable_info(callable_var_positional)
    assert info.id == id(callable_var_positional)
    assert info.named_args == frozenset()
    assert info.required_named_args == frozenset()
    assert info.requires_positional
    assert not info.kwargs
    assert not info.supports_zero_args


def callable_all_types(a: int, /, b: str, *, c: float = 1.0, **kwargs: t.Any) -> None:
    """Test callable that takes all types of arguments."""
    pass


def test_all_types() -> None:
    """Test that a callable that takes all types of arguments is detected."""
    info = get_callable_info(callable_all_types)
    assert info.id == id(callable_all_types)
    assert info.named_args == frozenset(["b", "c"])
    assert info.required_named_args == frozenset(["b"])
    assert info.requires_positional
    assert info.kwargs
    assert not info.supports_zero_args
