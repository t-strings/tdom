"""An expression which chooses subcomponent based on condition."""

from tdom import html


def DefaultHeading():
    """The default heading."""
    return html(t"<h1>Default Heading</h1>")


def OtherHeading():
    """Another heading used in another condition."""
    return html(t"<h1>Other Heading</h1>")


def Body(props, children):
    """Render the body with a heading based on which is passed in."""
    heading = props.get("heading")
    return html(t"<body>{heading if heading else DefaultHeading}</body>")


def main():
    """Main entry point."""
    result = html(t"<{Body} heading={OtherHeading}/>")
    return result
