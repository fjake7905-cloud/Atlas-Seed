# Contributing to Atlas-Seed

Thank you for considering contributing to Atlas-Seed!

## Development Setup

```bash
# Clone
git clone https://github.com/fjake7905-cloud/Atlas-Seed.git
cd Atlas-Seed

# Install in editable mode with dev deps
pip install -e .[dev]

# Run verification
python scripts/verify_atlas.py
python scripts/change_guard.py

# Run tests
python -m pytest -v

# Run linter
pylint $(git ls-files '*.py') --rcfile=pyproject.toml
```

## Project Structure

- `atlas.py` - CLI entrypoint REPL
- `runtime/` - Core runtime: state, planner, executor, memory, events, router, agent_loop
- `core/` - Tool registry and capabilities
- `agents/` - Agent implementations
- `tests/` - Unit and integration tests
- `scripts/` - Verification tooling

## Workflow (Phased Roadmap)

We follow a phased roadmap (Phase 1 → 10) with small atomic commits:

- **Phase 1:** Foundation & Integrity (manifest as single source, CI cleanup, version fix) ✅
- **Phase 2:** Security & Stability (CWD fix, run hardening) ✅
- **Phase 3:** Core API Hardening (EventBus, Capability, ToolRegistry) ✅
- **Phase 4:** File Tools Completion (shlex, multiline, append/delete/search) ✅
- **Phase 5:** Memory & State V2 (timestamp, id, stats) ✅
- **Phase 6:** Testing & Verification V2 (security suite) ✅
- **Phase 7:** DevOps & Packaging (pyproject.toml) 🚧 Current
- **Phase 8:** Intelligence Layer (Model Provider)
- **Phase 9:** CLI & Observability
- **Phase 10:** Scale & Multi-Workspace

See `ATLAS_PROJECT_PLAN.md` and `ATLAS_TOP20_AND_ROADMAP.md` for full roadmap.

## Rules from ATLAS_RULES.md

Before making any new change:

1. Read `README.md`
2. Read `ATLAS_RULES.md`
3. Read `atlas_manifest.json`
4. Read `scripts/change_guard.py`
5. Read `scripts/verify_atlas.py`
6. Check runtime, agent, core, test files related to change
7. Confirm change is already applied in repository
8. Run verification before moving on

Change policy:

- Do not treat a file as finished until it has code, test coverage, and verification.
- Do not create placeholder files unless they are part of current step.
- Every new feature must update the manifest and pass verification.
- Every new feature must be reflected in change report or verification path.

## Atomic Commits

- Create dedicated branch: `phase/N-name` or `feature/name`
- Make small, atomic commits (single concern per commit)
- Run all tests after every change: `python -m pytest -q && python scripts/verify_atlas.py`
- Fix failures before continuing
- Update documentation if necessary
- Open Pull Request with detailed explanation
- Do not start next phase until PR approved (unless instructed to continue)

## Verification

```bash
python scripts/change_guard.py
python scripts/verify_atlas.py
python -m pytest -v
```

All must PASS.

## Manifest as Single Source of Truth

- `atlas_manifest.json` lists all required components (now 24 files)
- `verify_atlas.py` loads manifest as primary source, fallback hard-coded list for safety
- `change_guard.py` checks manifest files exist
- When adding new file that is part of core, add it to manifest

## Notifications

This workspace includes `runtime/notifications.py` with Telegram → Email → File fallback chain.

Configure via:

```bash
export TELEGRAM_BOT_TOKEN="xxx"
export TELEGRAM_CHAT_ID="yyy"
# Or create .atlas/notification_config.json
```

See `NOTIFICATION_SETUP.md` and `reports/end_of_task_report.md`.

## Pull Request Process

1. Create branch from main
2. Implement with atomic commits
3. Ensure verification PASS and tests PASS after each commit
4. Push branch: `git push -u origin your-branch`
5. Open PR via GitHub with detailed body (see previous PRs #2-#7 for template)
6. Wait for review and approval
7. Merge via squash merge

Thank you!
