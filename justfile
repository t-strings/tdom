default: lint format_check type_check test

lint:
    uv run ruff check

format_check:
    uv run ruff format --check

type_check:
    uv run pyright

test:
    uv run pytest

watch:
    # Watch for changes and run tests.
    uv run ptw tdom/  

build_docs:
    cd docs && uv run sphinx-build . _build

clean_docs:
    rm -rf docs/_build

build_package:
    uv build

clean_package:
    rm -rf dist/

build: build_docs build_package

clean: clean_docs clean_package
