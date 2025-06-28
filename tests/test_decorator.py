import functools
import sys
from dataclasses import dataclass

import pytest
from venusian import Scanner, attach


@dataclass
class Registry:
    flag: int = 99

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
    assert 11 == target11()
    result = Target11()
    assert result.name == "bar11"


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
    assert target55() == "special: 55"
    inst = Target55()
    assert inst.flag == "special"

# ------- 6: Generic args and kwargs

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

    assert target66() == "special: 99 66"
    inst = Target66()
    assert inst.flag == "special"
    assert inst.registry.flag == 99

# -------
# class MyClassDecorator:
#     def __init__(self, *a, **kw):
#         self.conf_args = a
#         self.conf_kw = kw
#         # self.func  = None
#
#     def __call__(self, func):
#         # self.func = func
#         def wrapper(*args, **kwargs):
#             if args:
#                 if isinstance(args[0], int):
#                     a = list(args)
#                     a[0] += 5
#                     args = tuple(a)
#                     print('preprocess OK', args)
#             r = func(*args, **kwargs)
#             print('postprocessing', r)
#             r += 7
#             return r
#         return wrapper
#
#
# @MyClassDecorator(1001,a='some configuration')
# def my_function(first, second):
#     print('call my_function', first, second)
#     return 3 + first + second
#
# @MyClassDecorator(1001,a='some configuration')
# @dataclass
# class MyClass:
#     first: int
#     second: int
#
#     def __call__(self):
#         return 3 + self.first + self.second
#
# def test_example_function():
#     result = my_function(1, 2)
#     assert result == 18
#
# def test_example_class():
#     inst = MyClass(1, 2)
#     result = inst()
#     assert result == 18