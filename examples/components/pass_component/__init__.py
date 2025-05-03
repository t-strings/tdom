"""Pass a component as a prop value."""

from tdom import html


def DefaultHeading(props, children):
    """The default heading."""
    return html(t"<h1>Default Heading</h1>")


def Body(props, children):
    """The body which renders the heading."""
    heading = props["heading"]
    return html(t"<body><{heading} /></body>")


def main():
    """Main entry point."""
    result = html(t"<{Body} heading={DefaultHeading} />")
    return result
