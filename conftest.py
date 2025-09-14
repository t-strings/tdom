# Configure Sybil for testing code in documentation examples


from sybil import Sybil
from sybil.parsers.myst import PythonCodeBlockParser

pytest_collect_file = Sybil(
    parsers=[PythonCodeBlockParser()],
    patterns=[
        "*.md",
    ],
).pytest()
