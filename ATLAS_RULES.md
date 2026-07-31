# Atlas Rules

## Core workflow

Before making any new change:

1. Read `README.md`.
2. Read `ATLAS_RULES.md`.
3. Read `atlas_manifest.json`.
4. Read `scripts/change_guard.py`.
5. Read `scripts/verify_atlas.py`.
6. Check the runtime, agent, core, and test files related to the change.
7. Confirm the change is already applied in the repository.
8. Run verification before moving on.

## Change policy

- Do not treat a file as finished until it has code, test coverage, and verification.
- Do not create placeholder files unless they are part of the current step.
- Every new feature must update the manifest and pass verification.
- Every new feature must be reflected in the change report or verification path.

## Project direction

Atlas should evolve as a practical agent system with:

- a CLI entrypoint,
- a planner,
- an executor,
- an agent loop,
- verification tooling,
- and GitHub-backed history.
