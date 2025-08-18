import functools
import sys
from dataclasses import dataclass
from inspect import signature

import pytest
from venusian import Scanner, attach


@dataclass
class Registry:
    # A way to test that execution of a component occurred
    flag: int = 99
    # Simulate the various registered services
    services: int = 0


@pytest.fixture
def registry() -> Registry:
    return Registry()


@pytest.fixture
def scanner(registry) -> Scanner:
    s = Scanner(registry=registry)
    current_module = sys.modules[__name__]
    s.scan(current_module)
    return s


# ------- 1: Basic minimum decorator


def injectable11(wrapped):
    return wrapped


@injectable11
def target11() -> int:
    return 11


@injectable11
@dataclass
class Target11:
    name: str = "bar11"


def test_initial_call():
    # Assert both function and class targets
    assert 11 == target11()
    inst = Target11()
    assert inst.name == "bar11"


# ------- 2: Class-based decorator


class injectable22:
    def __init__(self):
        pass

    def __call__(self, wrapped):
        functools.update_wrapper(self, wrapped)
        return wrapped


@injectable22()
def target22():
    return 22


@injectable22()
@dataclass
class Target22:
    name: str = "bar22"


def test_class_decorator():
    # Assert both function and class targets
    assert target22() == 22
    result = Target22()
    assert result.name == "bar22"


# ------- 3: Decorator has a default argument


class injectable33:
    def __init__(self, flag: str = "default"):
        self.flag = flag

    def __call__(self, wrapped):
        def _wrapped(*args, **kwargs):
            _wrapped_result = wrapped(flag=self.flag)
            return _wrapped_result

        return _wrapped


@injectable33()
def target33(flag: str):
    return f"{flag}: 33"


@injectable33()
@dataclass
class Target33:
    flag: str | None = None


def test_class_decorator_default_args():
    # Assert both function and class targets
    assert target33() == "default: 33"
    inst = Target33()
    assert inst.flag == "default"


# ------- 4: Decorator argument is actually passed


class injectable44:
    def __init__(self, flag: str = "default"):
        self.flag = flag

    def __call__(self, wrapped):
        def _wrapped(*args, **kwargs):
            _wrapped_result = wrapped(flag=self.flag)
            return _wrapped_result

        return _wrapped


@injectable44(flag="special")
def target44(flag: str):
    return f"{flag}: 44"


@injectable44(flag="special")
@dataclass
class Target44:
    flag: str | None = None


def test_class_decorator_pass_args():
    # Assert both function and class targets
    assert target44() == "special: 44"
    inst = Target44()
    assert inst.flag == "special"


# ------- 5: Generic args and kwargs


class injectable55:
    def __init__(self, flag: str = "default"):
        self.flag = flag

    def __call__(self, wrapped):
        def _wrapped(*args, **kwargs):
            _kwargs = kwargs.copy()
            _kwargs["flag"] = self.flag
            _wrapped_result = wrapped(*args, **_kwargs)
            return _wrapped_result

        return _wrapped


@injectable55(flag="special")
def target55(flag: str):
    return f"{flag}: 55"


@injectable55(flag="special")
@dataclass
class Target55:
    flag: str | None = None


def test_class_decorator_generic_args():
    # Assert both function and class targets
    assert target55() == "special: 55"
    inst = Target55()
    assert inst.flag == "special"


# ------- 6: Decorator args plus scanner support


class injectable66:
    def __init__(self, flag: str = "default"):
        self.flag = flag
        self.registry: Registry | None = None

    def __call__(self, wrapped):
        def _wrapped(*args, **kwargs):
            _kwargs = kwargs.copy()
            _kwargs["flag"] = self.flag
            _kwargs["registry"] = self.registry
            _wrapped_result = wrapped(*args, **_kwargs)
            return _wrapped_result

        def venusian_callback(scanner, name, ob):
            self.registry = getattr(scanner, "registry")
            # Simulate registering the target with the registry
            self.registry.services = 55

        attach(_wrapped, venusian_callback)

        return _wrapped


@injectable66(flag="special")
def target66(flag: str, registry: Registry):
    return f"{flag}: {registry.flag} 66"


@injectable66(flag="special")
@dataclass
class Target66:
    flag: str | None = None
    registry: Registry | None = None


def test_scanner_support(scanner: Scanner):
    this_registry = getattr(scanner, "registry")
    # Immediately upon scanner.scan, the decorator registers with the
    # registry. Make sure this is true.
    assert this_registry.services == 55

    # Assert both function and class targets
    assert target66() == "special: 99 66"
    inst = Target66()
    assert inst.flag == "special"
    assert inst.registry.flag == 99


# ------- 7: Refactor scanner callback into a method
class injectable77:
    def __init__(self, flag: str = "default"):
        self.flag = flag
        self.registry: Registry | None = None

    def venusian_callback(self, scanner: Scanner, name: str, ob: object):
        """Make it easier to create custom decorators through subclassing."""
        self.registry = getattr(scanner, "registry")
        # Simulate registering the target with the registry
        self.registry.services = 55

    def __call__(self, wrapped):
        @functools.wraps(wrapped)
        def _wrapped(*args, **kwargs):
            _kwargs = kwargs.copy()
            _kwargs["flag"] = self.flag
            _kwargs["registry"] = self.registry
            _wrapped_result = wrapped(*args, **_kwargs)
            return _wrapped_result

        def _venusian_callback(scanner: Scanner, name: str, ob: object):
            """Basically a lambda."""
            self.venusian_callback(scanner, name, ob)

        attach(_wrapped, _venusian_callback)

        return _wrapped


@injectable77(flag="special")
def target77(flag: str, registry: Registry):
    return f"{flag}: {registry.flag} 77"


@injectable77(flag="special")
@dataclass
class Target77:
    flag: str | None = None
    registry: Registry | None = None


def test_check_target_arguments(scanner: Scanner):
    this_registry = getattr(scanner, "registry")
    # Immediately upon scanner.scan, the decorator registers with the
    # registry. Make sure this is true.
    assert this_registry.services == 55

    # Assert both function and class targets
    assert target77() == "special: 99 77"
    inst = Target77()
    assert inst.flag == "special"
    assert inst.registry.flag == 99


# ------- 8: Pass registry/container into the target, if requested
class injectable88:
    def __init__(self, flag: str = "default"):
        self.flag = flag
        self.registry: Registry | None = None

    def venusian_callback(self, scanner: Scanner, name: str, ob: object):
        """Make it easier to create custom decorators through subclassing."""
        self.registry = getattr(scanner, "registry")
        # Simulate registering the target with the registry
        self.registry.services = 55

    def __call__(self, wrapped):
        param_names = [param.name for param in signature(wrapped).parameters.values()]

        @functools.wraps(wrapped)
        def _wrapped(*args, **kwargs):
            if self.registry is None:
                return wrapped(*args, **kwargs)
            _kwargs = kwargs.copy()

            # Let's inject the registry only if it is asked for
            if "registry" in param_names:
                _kwargs["registry"] = self.registry

            _wrapped_result = wrapped(*args, **_kwargs)
            return _wrapped_result

        def _venusian_callback(scanner: Scanner, name: str, ob: object):
            """Basically a lambda."""
            self.venusian_callback(scanner, name, ob)

        attach(_wrapped, _venusian_callback)

        return _wrapped


@injectable88(flag="special")
def target88(registry: Registry):
    return f"{registry.flag} 88"


@injectable88(flag="special")
@dataclass
class Target88:
    registry: Registry | None = None


def test_sniff_target_signature(scanner: Scanner):
    # Assert both function and class targets
    assert target88() == "99 88"
    inst = Target88()
    assert inst.registry.flag == 99


# ------- 9: Refactor building args and calling target
class injectable99:
    def __init__(self, flag: str = "default"):
        self.flag = flag
        self.registry: Registry | None = None
        self.param_names: list[str] = []

    def venusian_callback(self, scanner: Scanner, name: str, ob):
        """Make it easier to create custom decorators through subclassing."""
        # Let's sniff the target signature only once, instead of every call.
        self.param_names = [param.name for param in signature(ob).parameters.values()]

        self.registry = getattr(scanner, "registry")
        # Simulate registering the target with the registry
        self.registry.services = 55

    def make_args(self, these_kwargs):
        _kwargs = these_kwargs.copy()

        # Let's inject the registry only if it is asked for
        if "registry" in self.param_names:
            _kwargs["registry"] = self.registry

        return _kwargs

    def call_target(self, target, **these_kwargs):
        """Customize the calling and post-processing of a target."""
        result = target(**these_kwargs)
        return result

    def __call__(self, wrapped):
        @functools.wraps(wrapped)
        def _wrapped(*args, **kwargs):
            _kwargs = self.make_args(kwargs)
            result = self.call_target(wrapped, **_kwargs)
            return result

        def _venusian_callback(scanner: Scanner, name: str, ob):
            """Basically a lambda."""
            self.venusian_callback(scanner, name, ob)

        attach(_wrapped, _venusian_callback)

        return _wrapped


@injectable99(flag="special")
def target99(registry: Registry):
    return f"{registry.flag} 99"


@injectable99(flag="special")
@dataclass
class Target99:
    registry: Registry | None = None


def test_refactor_make_args_and_call(scanner: Scanner):
    # Assert both function and class targets
    assert target99() == "99 99"
    inst = Target99()
    assert inst.registry.flag == 99


# ------- 10: Handle args/props passed from the caller
class injectable100:
    def __init__(self, flag: str = "default"):
        self.flag = flag
        self.registry: Registry | None = None
        self.param_names: list[str] = []

    def venusian_callback(self, scanner: Scanner, name: str, ob):
        """Make it easier to create custom decorators through subclassing."""
        # Let's sniff the target signature only once, instead of every call.
        self.param_names = [param.name for param in signature(ob).parameters.values()]

        self.registry = getattr(scanner, "registry")
        # Simulate registering the target with the registry
        self.registry.services = 55

    def make_args(self, these_kwargs):
        _kwargs = these_kwargs.copy()

        # Let's inject the registry only if it is asked for
        if "registry" in self.param_names:
            _kwargs["registry"] = self.registry

        return _kwargs

    def call_target(self, target, **these_kwargs):
        """Customize the calling and post-processing of a target."""
        result = target(**these_kwargs)
        return result

    def __call__(self, wrapped):
        @functools.wraps(wrapped)
        def _wrapped(*args, **kwargs):
            _kwargs = self.make_args(kwargs)
            result = self.call_target(wrapped, **_kwargs)
            return result

        def _venusian_callback(scanner: Scanner, name: str, ob):
            """Basically a lambda."""
            self.venusian_callback(scanner, name, ob)

        attach(_wrapped, _venusian_callback)

        return _wrapped


@injectable100(flag="special")
def target100(name: str, registry: Registry):
    return f"Name: {name}"


@injectable100(flag="special")
@dataclass
class Target100:
    registry: Registry | None = None


def test_pass_props(scanner: Scanner):
    # Assert both function and class targets
    assert target100(name="this_name") == "Name: this_name"
    inst = Target100()
    assert inst.registry.flag == 99
