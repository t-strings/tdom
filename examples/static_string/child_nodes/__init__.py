"""Child nodes become part of the structure."""
from tdom import html


def main():
    """Main entry point."""
    structure = html(t"<div>Hello <span>World<em>!</em></span></div>")
    return structure
