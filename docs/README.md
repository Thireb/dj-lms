# LMS project docs

Plain-language docs for building a multi-institute LMS in Django.

| File | What it is |
|---|---|
| `FEATURES.md` | Every feature, by portal, with checkboxes |
| `ARCHITECTURE.md` | Django apps, models, tenancy, jobs |
| `UI-GUIDELINES.md` | Colors, layout, page patterns, UI rules |
| `COMPONENTS.md` | Python class-based components, crispy-forms, page classes |
| `SPEC-DETAILS.md` | Table columns, form fields, statuses, rules, PDFs, notifications, seed data (assumed) |
| `CURSOR-PROMPTS.md` | Ready prompts, one per Cursor session |
| `.cursor/rules/lms.mdc` | Always-on Cursor rule file |
| `AGENTS.md` | Rules for AI coding agents (put in repo root) |
| `ROADMAP.md` | Build order, phase by phase |
| `DEPLOYMENT.md` | Render setup and checklist |

## How to use

1. Create the repo and copy these files into `docs/` (move `AGENTS.md` to the root).
2. Give an agent one roadmap item at a time.
3. Start with `CURSOR-PROMPTS.md` session 1.
4. When demo details are confirmed, update `SPEC-DETAILS.md` first, then the code.

## Source material

Cursor captured the reference's public pages into the WebScraping101 repo (`raw/` and `requirements/`). Use them to read, never to copy. Nothing in them was seen on a logged-in session (login is behind Cloudflare Turnstile).

## Ground rules

- Copy features, not content, branding, or text.
- Zoom comes later and needs a paid account.
- Pure Django templates first; a JS framework only if needed.
- UI is built from Python component classes and crispy-forms, reused by inheritance.
