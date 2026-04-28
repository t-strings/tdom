import string
from contextvars import ContextVar

from .cvar_utils import ContextVarSetter

CtxStr = ContextVar[str]("CtxStr", default="default")
CtxInt = ContextVar[int]("CtxInt", default=0)


def _assert_ctx(ctx_str: str = "default", ctx_int: int = 0):
    assert CtxStr.get() == ctx_str
    assert CtxInt.get() == ctx_int


def test_set():
    _assert_ctx()
    with ContextVarSetter(
        context_values=(
            (CtxStr, "new"),
            (CtxInt, 1),
        )
    ):
        _assert_ctx("new", 1)
    _assert_ctx()


def test_nest():
    _assert_ctx()
    with ContextVarSetter(
        context_values=(
            (CtxStr, "new"),
            (CtxInt, 1),
        )
    ):
        _assert_ctx("new", 1)
        with ContextVarSetter(
            context_values=(
                (CtxStr, "again"),
                (CtxInt, 2),
            )
        ):
            _assert_ctx("again", 2)
        _assert_ctx("new", 1)
    _assert_ctx()


def test_reps():
    _assert_ctx()
    for index, leter in enumerate(string.ascii_lowercase):
        with ContextVarSetter(
            context_values=(
                (CtxStr, leter),
                (CtxInt, index),
            )
        ):
            _assert_ctx(leter, index)
        _assert_ctx()


def test_empty():
    _assert_ctx()
    with ContextVarSetter(context_values=()):
        # DO NOTHING BUT NOT AN ERROR
        _assert_ctx()
    _assert_ctx()


def test_one():
    _assert_ctx()
    with ContextVarSetter(context_values=((CtxStr, "new"),)):
        _assert_ctx("new")
    _assert_ctx()
