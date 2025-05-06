"""A variation of the to do list, possibly duplicated in another example."""
from tdom import html
from viewdom import render


def Todo(label):
    """An individual to do component."""
    return html(t"<li>{label}</li>")


def TodoList(todos):
    """A to do list component."""
    return html(t"<ul>{[Todo(label) for label in todos]}</ul>")


def TodoApp(title, todolist):
    """A to do list application."""
    return html(t"<h1>{title}</h1>{todolist}")


def main():
    """Main entry point."""
    todos = ["first"]
    todo_list = TodoList(todos)
    return render(
        html(
            """
      <{TodoApp} title="My Todos" todolist={todo_list} />
    """
        )
    )


result = main()
expected = "<h1>My Todos</h1><ul><li>first</li></ul>"


def main():
    """Main entry point."""
    return result
