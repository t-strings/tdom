from tdom import Element, Text, html
from tdom.types import Context


def test_context_passed_to_component_simple():
    calls: list[dict[str, object] | None] = []

    def Comp(*children: Text, answer: int, context: Context = None):
        calls.append(context)
        return Text(f"answer={answer},ctx={context['x'] if context else 'None'}")

    html(t"<div><{Comp} answer={42} /></div>", context={"x": 7})
    assert calls == [{"x": 7}]


def test_context_passed_to_subcomponent_via_template():
    seen: list[object] = []

    def Child(*children: Text, context: Context = None):
        seen.append(context and context.get("user"))
        return Text("child")

    def Parent(*children: Text, context: Context = None):
        # Parent returns a Template that invokes Child; context should flow.
        return t"<section><{Child} /></section>"

    html(t"<main><{Parent} /></main>", context={"user": "alice"})
    assert seen == ["alice"]


def test_context_not_required_for_component():
    # Component does not accept `context`; passing context to html() should not break.
    def NoCtx(*children: Text, answer: int):
        return Text(f"answer={answer}")

    node = html(t"<div><{NoCtx} answer={42} /></div>", context={"x": 7})
    # Fake out PyCharm's type checker
    children = getattr(node, "children")
    assert children[0].text == "answer=42"
