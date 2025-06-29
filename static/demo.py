from tdom import html


def main():
    """Return strings to be shoved into the DOM."""

    def Header(children):
        return html(t"<main>{children}</main>")
    t_strings = "t-strings"
    result = str(html(t"<{Header}><h1>Hello {t_strings} 🥳</h1><//>"))
    return result