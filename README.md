# Atlas-Seed

Initial bootstrap for the Atlas autonomous agent platform.

## Verify the repository

Run the built-in verification tool from the repository root:

```bash
python scripts/verify_atlas.py
```

This checks that the core Atlas files exist and that the current runtime pieces are present.

## GitHub Actions

A workflow also runs the same verification on every push and pull request.

## CLI

The Atlas shell supports basic workspace and file commands, plus memory inspection:

- `memory` to show recent actions
- `memory search <text>` to find matching history entries
