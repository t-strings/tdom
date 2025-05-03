"""Subcomponents."""

from tdom import html

title = "My Todos"


def Todo(label):
    """An individual to do component."""
    return html(t"<li>{label}</li>")


def TodoList(props, children):
    """A to do list component."""
    todos = props["todos"]
    # Pass an argument, not the normal props style
    return html(t"<ul>{[Todo(label) for label in todos]}</ul>")


def main():
    """Main entry point."""
    todos = ["first"]
    return html(
        t"""
      <h1>{title}</h1>
      <{TodoList} todos={todos} />
    """
    )
