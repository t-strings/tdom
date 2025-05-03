"""Overriding a default "built-in" component."""

from tdom import html


def DefaultHeading():  # pragma: nocover
    """The default heading."""
    return html(t"<h1>Default Heading</h1>")


def OtherHeading(props, children):
    """Another heading used in another condition."""
    return html(t"<h1>Other Heading</h1>")


def Body(props, children):
    """Render the body with a heading based on which is passed in."""
    heading = props["heading"]
    return html(t"<body><{heading} /></body>")


def main():
    """Main entry point."""
    result = html(t"<{Body} heading={OtherHeading}/>")
    return result
