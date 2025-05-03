"""Prop values from scope variables."""
from tdom import html


def Heading(props, children):
    """The default heading."""

    title = props["title"]
    return html(t"<h1>{title}</h1>")


this_title = "My Title"


def main():
    """Main entry point."""
    result = html(t"<{Heading} title={this_title} />")
    return result
