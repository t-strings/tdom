"""Sphinx configuration."""

from datetime import datetime

project = "tdom"
author = "Dave Peck, Andrea Giammarchi, and Paul Everitt"
copyright = f"{datetime.now().year}, {author}"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]
autodoc_typehints = "description"
html_theme = "furo"
myst_enable_extensions = ["colon_fence"]
linkcheck_allowed_redirects = {}
html_title = "tdom"
suppress_warnings = ["misc.highlighting_failure"]
