default: lint format_check format_docs_check type_check test

lint:
    uv run ruff check

format_check:
    uv run ruff format --check

format_docs:
    npx prettier --write README.md "docs/**/*.md"

format_docs_check:
    npx prettier --check README.md "docs/**/*.md"

type_check_pyright:
    uv run pyright

type_check_ty:
    uv run ty check

type_check: type_check_pyright type_check_ty

test:
    uv run pytest

# Test the CI Python matrix without replacing the development .venv.
test-matrix:
    #!/usr/bin/env sh
    set -eu
    uv python install --no-bin 3.14.6
    uv python install --upgrade --no-bin 3.14 3.15
    result=0
    # Keep in sync with the CI and PyPI workflow matrices.
    for version in 3.14.6 3.14 3.15; do
        uv run --isolated --locked --managed-python --python "$version" pytest -v || result=1
    done
    exit "$result"

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

# Open a version-bump PR from origin/main (requires git, uv, and authenticated gh).
[positional-arguments]
release-pr version:
    #!/usr/bin/env sh
    set -eu
    if [ -n "$(git status --porcelain)" ]; then
        echo "Commit or stash your changes before preparing a release." >&2
        exit 1
    fi
    version=$(uv version "$1" --dry-run --short)
    git fetch origin main
    git switch --no-track -c "release/v$version" origin/main
    uv version "$version" --no-sync
    git add pyproject.toml uv.lock
    git commit -m "Bump version to $version"
    git push -u origin HEAD
    gh pr create --base main --head "release/v$version" --title "Release v$version" --body "Bump the package version to $version. Publish the GitHub release after this PR passes CI and merges."

# Publish the version on origin/main; the GitHub release starts the PyPI workflow.
release:
    #!/usr/bin/env sh
    set -eu
    if [ -n "$(git status --porcelain)" ]; then
        echo "Commit or stash your changes before publishing a release." >&2
        exit 1
    fi
    git switch main
    git pull --ff-only origin main
    if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
        echo "Local main has unpublished commits; release from origin/main only." >&2
        exit 1
    fi
    version=$(uv version --short)
    git tag "v$version"
    git push origin "refs/tags/v$version"
    gh release create "v$version" --verify-tag --generate-notes

reports:
    uv run pytest --cov=tdom --cov-report=xml:reports/coverage.xml --cov-report=term --cov-report=html:reports/coverage --junitxml=reports/pytest.xml --html=reports/pytest.html

clean_reports:
    rm -rf reports/

badges:
    uv run genbadge tests -i reports/pytest.xml -v -o reports/pytest.svg
    uv run genbadge coverage -i reports/coverage.xml -v -o reports/coverage.svg

clean_badges:
    rm -rf reports/*.svg
