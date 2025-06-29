from tdom import html


def main():
    name = "World"
    result = html(t"<div>Hello {name}</div>")
    return str(result)