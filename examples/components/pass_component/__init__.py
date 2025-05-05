"""Pass a component as a prop value."""

from tdom import html


def DefaultHeading():
    """The default heading."""
    return html(t"<h1>Default Heading</h1>")


def Body(heading):
    """The body which renders the heading."""
    return html(t"<body><{heading} /></body>")


def main():
    """Main entry point."""
    result = html(t"<{Body} heading={DefaultHeading} />")
    return result
