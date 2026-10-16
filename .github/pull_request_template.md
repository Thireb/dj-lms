## Summary

<!-- What this PR builds or fixes, in 2 to 5 bullets. -->

## Roadmap and backlog

<!-- Roadmap items (for example 5.4 part 2) and backlog ids (for example AS10) this PR covers. -->

## Deviations from docs

<!-- Required. List each "(assumed)" choice, each gap in the docs, and each part left out on purpose, with the doc and section. Write "None" only when there is none. -->

## Checks

- pytest:
- ruff check / ruff format --check:
- makemigrations --check:
- Mutation check:
- Browser probe (360px and 1440px):

## Security pass

- Tenant isolation:
- Access control (`allowed_roles`, `MenuRequiredMixin`):
- Output escaping:
- CSRF:
