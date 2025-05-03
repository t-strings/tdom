"""Optional props."""
from tdom import html


def Heading(props, children):
    """The default heading."""

    # TODO This would be nicer if title was in function signature with
    #    default, as in ViewDOM.
    title = props.get("title", "My Title")
    return html(t"<h1>{title}</h1>")


def main():
    """Main entry point."""
    result = html(t"<{Heading} />")
    return result
