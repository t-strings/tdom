"""The simplest-possible use of injectable, no html()."""

from dataclasses import dataclass

from svcs import Container

from tdom import html
from tdom.decorators import injectable


@injectable()
@dataclass
class MyClassHeader:
    container: Container
    name: str = "World"

    def __call__(self) -> str:
        salutation = "Hello"
        return html(t"<span>{salutation}</span>: {self.name}")
