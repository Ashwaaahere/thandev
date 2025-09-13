# Contributing to Thandev

Thanks for your interest!

## Workflow
1. Fork the repo & create a feature branch.
2. Write tests where applicable.
3. Run lint/format: `ruff` + `black` (backend), `eslint` + `prettier` (frontend).
4. Open a PR using our PR template.

## Commit Conventions
- Conventional commits are recommended:
  - `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`

## Dev Setup
- Use `docker compose up --build` for a full local stack.
- Backend tools available inside container:
  - `uvicorn`, `pytest`, `ruff`, `black`
- Frontend tools inside container:
  - `next`, `eslint`, `prettier`

## Issues & Discussions
- Use **Bug report** or **Feature request** templates.
- Security vulnerabilities: **Do not open a public issue** — see SECURITY.md.
