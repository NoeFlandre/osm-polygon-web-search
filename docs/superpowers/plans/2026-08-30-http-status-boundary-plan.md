# HTTP status boundary refactor

## Goal

Remove the identical HTTP 2xx check from the Brave search and page-fetch
adapters without changing exceptions, messages, outputs, retry behavior, or
public constructor and method signatures.

## TDD sequence

1. Add a focused contract test for the shared status predicate and confirm it
   fails because the predicate does not exist.
2. Add the smallest predicate implementation and confirm the focused test
   passes.
3. Replace both duplicated adapter checks with the predicate and run the
   adapter regression tests.
4. Run coverage, Ruff, ty, pre-commit, strict MkDocs, mutation testing,
   packaging, Docker, and repository hygiene checks.

## Scope

Only `http.py`, `fetch.py`, `search.py`, and their tests are in scope. The
predicate keeps the existing inclusive 200 and exclusive 300 semantics. No
new network behavior, validation policy, or abstraction is introduced.
