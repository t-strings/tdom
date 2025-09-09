# t-strings and tdom: Project-specific guidelines

These guidelines are tailored for contributors and maintainers of the tdom
project. They complement, not replace, the README and docs. Keep changes minimal
and focused; prefer incremental PRs.

First, read `.junie/pep-0750.rst` to learn more about t-strings.

## t-strings

- t-string means template string which refers to a PEP 750 feature added in
  Python 3.14.
- A template function is a normal Python that is passed a template object
- The type Template is imported from string.templatelib in the Python standard
  library
- string.templatelib also contains a type Interpolation which is used for the
  dynamic parts in a template instance
- Template functions, also called t-string functions, are passed a
  `string.templatelib.Template` object and return a string.
- Always return a string that combines the parts.
- These t-strings contain static string part and interpolation parts.
- Use structural pattern matching, as shown in the PEP examples, when analyzing
  the parts.
- Always use type hints on the function arguments and return values.

## tdom

- This project has many examples that I want you to read in the examples
  directory and subdirectories.

## Project scope

- tdom is an HTML/SVG templating/runtime for Python t-strings (PEP 750),
  targeting Python 3.14+ SSR
- Public artifacts: PyPI package, Sphinx docs (GitHub Pages), examples
  playground, and browser-based tests via pytest-playwright.

## Supported environments

- Python: 3.14 only (see requires-python in pyproject.toml). Use uv for env
  management.

## Code style and quality

- Python: ruff for linting; black (pep750-support branch) for formatting. Run
  ruff/black before committing when possible.
- Keep public API minimal and documented. Update **all** where relevant.
- Prefer small, pure functions; avoid side effects except where needed by
  runtime.
- Performance matters: avoid per-render allocations in hot paths; reuse parsed
  templates and caches (\_parsed, listeners) responsibly.
- Typing is optional; add when it clarifies behavior. Keep runtime lightweight
  (no extra deps in [project]).

## Tests

- All new features must include tests. Place unit tests in tests/ and
  example-backed tests under examples/ when appropriate.
- Use the integration marker for Playwright/browser tests; keep default test run
  fast.
- Examples double as tests; keep examples minimal, deterministic, and readable.
- If adding fixtures, consider integrating with existing tdom.fixtures and
  network interception approach.
- The tests use pytest. Where appropriate, make fixtures in `tests/conftest.py`
  and use them in a test.

## Documentation

- User-facing behavior must be reflected in docs/ and README.md.
- Short how-to examples go in docs/examples and are linked from docs/index.md
  toctree.
- Keep docs buildable offline: avoid external fetches during sphinx-build. Use
  myst markdown.

## Examples and playground

- Each example directory should be self-contained with an index.tdom.py or
  similar Python snippet compatible with the playground loader.
- Favor clarity over cleverness; examples are learning resources and test
  fixtures.

## API design principles

- Maintain stable names: html, svg, render, parse, unsafe, DOM node classes and
  constants.
- Backward compatibility: avoid breaking changes to function signatures and
  return structures without deprecation notes.
- Handle edge cases in template updates: attributes vs content vs comments;
  ensure cloning and change application semantics remain consistent.

## Branching, commits, PRs

- Branch: feature/<short-description>, fix/<short-description>, docs/<topic>.
- Commits: concise, imperative subject; include context when touching runtime
  performance or caching behavior.
- PRs: include rationale, tests, and docs updates

## Versioning and release

- SemVer-ish pre-1.0: bump minor for features, patch for fixes/docs.
- Keep pyproject.toml version in sync with CHANGELOG/releases. Avoid API breaks
  without coordination.

## Security and safety

- unsafe should be used explicitly; default flows must avoid executing or
  trusting unescaped HTML. Keep clear docstrings and docs warnings.
- Avoid introducing dynamic code execution and external network accesses in
  library code.

## When modifying core runtime (src/tdom)

- Respect the parsing/cache contract: \_parse returns (content, updates);
  cloning and update application must be efficient.
- Maintain listener lifecycle: \_listeners cleared once per render; avoid leaks.
- Keep DOM node shapes and constants stable; update **all** if adding/removing.

## Contributing checklist (PR ready)

- [ ] Tests added/updated and passing (fast suite mandatory; integration if
      applicable)
- [ ] Docs/README updated if behavior or API changes
- [ ] Examples updated/added if user-facing
- [ ] Ruff/black run locally
- [ ] Performance considerations noted (bench or reasoning) if touching hot path
- [ ] No new runtime dependencies

If something in these guidelines conflicts with real-world constraints, open an
issue to discuss exceptions. Keep changes small and focused.
