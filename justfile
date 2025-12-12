# Justfile for tdom
# Requires: just, uv, Python 3.14
# All tasks use uv to ensure isolated, reproducible runs.

# Default recipe shows help
default:
    @just --list

# Print environment info
info:
    @echo "Python: $(python --version)"
    @uv --version

# Install project and dev dependencies
install:
    uv sync --all-groups

# Alias for install (better discoverability)
setup: install

# Run tests (sequential)
test *ARGS:
    uv run pytest {{ ARGS }}

# Run tests (parallel)
test-parallel *ARGS:
    uv run pytest -n auto {{ ARGS }}

# Lint code (check for issues)
lint *ARGS:
    uv run ruff check {{ ARGS }} .

# Format code (auto-format)
fmt *ARGS:
    uv run ruff format {{ ARGS }} .

# Check formatting without modifying files (for CI)
fmt-check *ARGS:
    uv run ruff format --check {{ ARGS }} .

# Lint and auto-fix
lint-fix:
    uv run ruff check --fix .

# Type checking
typecheck *ARGS:
    uv run pyright {{ ARGS }}

# Build the documentation site
docs:
    uv run sphinx-build -b html docs docs/_build/html

# Format markdown files
fmt-docs:
    npx prettier --write "**/*.md"

# Watch for changes and run tests
watch:
    uv run ptw tdom/

# Build sdist/wheel
build:
    uv build

# Clean build and cache artifacts
clean:
    rm -rf .pytest_cache .ruff_cache .pyright .mypy_cache build dist
    find docs/_build -mindepth 1 -maxdepth 1 -not -name ".gitkeep" -exec rm -rf {} + || true
    rm -rf reports/

# Run all quality checks with fail-fast behavior
ci-checks:
    just install && just lint && just fmt-check && just typecheck && just test-parallel

# Generate reports for badges
reports:
    uv run pytest --cov=tdom --cov-report=xml:reports/coverage.xml --cov-report=term --cov-report=html:reports/coverage --junitxml=reports/pytest.xml --html=reports/pytest.html

# Generate badge SVGs from reports
badges:
    uv run genbadge tests -i reports/pytest.xml -v -o reports/pytest.svg
    uv run genbadge coverage -i reports/coverage.xml -v -o reports/coverage.svg

# Enable pre-push hook to run ci-checks before pushing
enable-pre-push:
    @echo "Installing pre-push hook..."
    @echo '#!/bin/sh' > .git/hooks/pre-push
    @echo '' >> .git/hooks/pre-push
    @echo '# Run quality checks before push' >> .git/hooks/pre-push
    @echo 'echo "Running quality checks before push..."' >> .git/hooks/pre-push
    @echo 'if ! just ci-checks; then' >> .git/hooks/pre-push
    @echo '    echo "Pre-push check failed! Push aborted."' >> .git/hooks/pre-push
    @echo '    exit 1' >> .git/hooks/pre-push
    @echo 'fi' >> .git/hooks/pre-push
    @chmod +x .git/hooks/pre-push
    @echo "Pre-push hook installed! Use 'just disable-pre-push' to disable."

# Disable pre-push hook
disable-pre-push:
    @chmod -x .git/hooks/pre-push 2>/dev/null || true
    @echo "Pre-push hook disabled. Use 'just enable-pre-push' to re-enable."
