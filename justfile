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

reports:
    uv run pytest --cov=tdom --cov-report=xml:reports/coverage.xml --cov-report=term --cov-report=html:reports/coverage --junitxml=reports/pytest.xml --html=reports/pytest.html

clean_reports:
    rm -rf reports/

badges:
    uv run genbadge tests -i reports/pytest.xml -v -o reports/pytest.svg
    uv run genbadge coverage -i reports/coverage.xml -v -o reports/coverage.svg

clean_badges:
    rm -rf reports/*.svg
