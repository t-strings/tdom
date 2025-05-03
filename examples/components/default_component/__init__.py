"""Overriding a default "built-in" component."""

from tdom import html


def DefaultHeading():  # pragma: nocover
    """The default heading."""
    return html(t"<h1>Default Heading</h1>")


def OtherHeading():
    """Another heading used in another condition."""
    return html(t"<h1>Other Heading</h1>")


def Body(heading):
    """Render the body with a heading based on which is passed in."""
    return html(t"<body><{heading} /></body>")


def main():
    """Main entry point."""
    result = html(t"<{Body} heading={OtherHeading}/>")
    return result
