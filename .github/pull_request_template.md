## Summary

<!-- What this PR builds or fixes, in 2 to 5 bullets. -->

## Roadmap and backlog

<!-- Roadmap items (for example 5.4 part 2) and backlog ids (for example AS10) this PR covers. -->

## Deviations from docs

<!-- Required. List each "(assumed)" choice, each gap in the docs, and each part left out on purpose, with the doc and section. Write "None" only when there is none. -->

## Checks

- pytest (parallel):
- pytest (serial, phase audits and fix branches):
- ruff check / ruff format --check:
- makemigrations --check:
- Mutation check (every catch confirmed):
- Browser probe (360px and 1440px):
- Failure modes checked (CLAUDE.md review step 4):

## Security pass

- Tenant isolation:
- Access control (`allowed_roles`, `MenuRequiredMixin`):
- Output escaping:
- CSRF:
