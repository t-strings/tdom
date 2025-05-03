"""Components can be any kind of dataclass_component."""

from dataclasses import dataclass

from tdom import html


@dataclass
class Greeting:
    """Give a greeting."""

    name: str

    def __call__(self):
        """Render to a string."""
        return f"Hello {self.name}"


def main():
    """Render a template to a string."""
    greeting = Greeting(name="viewdom")
    # TODO Teach the constructor to make dataclass components
    result = html(t"<div><{greeting} /></div>")
    return result
