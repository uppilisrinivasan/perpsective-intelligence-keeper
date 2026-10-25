# Contributing to lamina

Thanks for helping! Small, focused pull requests are easiest to review.

## Setup

    python -m venv .venv && .venv/bin/pip install -e .[test]
    .venv/bin/python -m pytest -q

## Review

- New behaviour needs tests. Run the whole suite before you push.
- Add a line to CHANGELOG.md under "Unreleased" for anything a user would notice.
- Public functions need docstrings.

## Loader notes

The loader has no cache on purpose. Ask before adding one.
