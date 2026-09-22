# Cleanup Roadmap

## Phase 1: Stabilize the live app

Goal: remove runtime surprises and make deployment repeatable.

Low-risk tasks:
- Keep route names, template references, and custom tag imports aligned.
- Expand regression tests around login, onboarding, payments, competition, and health checks.
- Standardize environment handling so local uses dev and deployment uses prod.
- Add deployment files such as `.env.example`, `.gitignore`, `Procfile`, and a deployment README.
- Use `python manage.py send_payment_reminders` from a platform scheduler instead of relying on in-code cron settings.

## Phase 2: Isolate business workflows

Goal: make the code easier to change without breaking other modules.

Low-risk tasks:
- Move registration, onboarding, payment posting, and batch assignment workflows into service modules.
- Keep views focused on request parsing, permissions, and response rendering.
- Move repeated email sending into reusable helpers with clear return values.
- Replace duplicated conditional status logic with shared helpers or constants.

## Phase 3: Reduce code drift

Goal: remove ambiguity in the repository.

Low-risk tasks:
- Decide whether `api/` will become a real DRF API or be archived.
- Remove dead imports, duplicate function definitions, and stale comments.
- Audit templates for route names that no longer exist.
- Trim unused JavaScript/package dependencies after confirming the CSS build still works.

## Phase 4: Harden production operations

Goal: make the app predictable in hosted environments.

Low-risk tasks:
- Add structured logging for mail failures, payment reminder runs, and competition staff actions.
- Add 404/500 templates and friendly fallback pages.
- Add deployment checks to CI: `check --deploy`, tests, CSS build, and collectstatic.
- Add database backups and media storage planning before production launch.

## Phase 5: Larger refactors after launch readiness

Goal: improve maintainability without blocking deployment.

Higher-effort tasks:
- Introduce a custom user model if role logic grows further.
- Split large templates into smaller reusable partials.
- Add a real API boundary if mobile or third-party clients are planned.
- Move background work to a task queue if reminder volume or PDF/email work grows.
