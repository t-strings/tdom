# Releasing tdom

Use a version-bump PR, then publish a GitHub release after it merges. You need
`git`, `uv`, `just`, and an authenticated GitHub CLI (`gh auth login`), with
`origin` pointing to `t-strings/tdom`. Start with a clean working tree.

1. Run `just release-pr 0.1.20` (substitute the version you want). This creates
   a branch from the latest `origin/main`, updates `pyproject.toml` and
   `uv.lock`, commits and pushes the change, and opens a PR.
2. Wait for all three Python CI checks to pass, then merge the PR on GitHub.
3. Run `just release`. This switches to `main`, pulls the merged changes, tags
   that version as `v0.1.20`, and publishes a GitHub release with generated
   notes. The existing publishing workflow tests all three Python versions,
   builds one wheel and source distribution, and publishes them to PyPI.

`just release` refuses unpublished local commits on `main` and existing local
tags. Neither command bypasses branch protection. The commands stop on errors;
if a network operation fails, inspect the output and resume the failed step. For
example, if the tag was pushed but release creation failed, run
`gh release create v0.1.20 --verify-tag --generate-notes`.

You can also publish the release through GitHub's web interface using the tag.
Publishing a saved draft triggers the same PyPI workflow.
