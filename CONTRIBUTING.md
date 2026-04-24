# Contributing

## Branch workflow

- `main` is always the deployable and review-passed branch.
- Start new work from the latest `main`.
- Use a focused branch name:
  - `feature/<topic>`
  - `fix/<topic>`
  - `chore/<topic>`

Example:

```powershell
git checkout main
git pull origin main
git checkout -b feature/obsidian-daily-template
```

## Commit workflow

Keep commits small and readable. Prefer one concern per commit.

Recommended commit prefixes:

- `feat:` new capability
- `fix:` bug fix
- `docs:` README or workflow docs
- `chore:` maintenance or tooling
- `refactor:` structural cleanup without behavior change

Examples:

- `feat: add training readiness note section`
- `fix: normalize Garmin Connect sync range`
- `docs: document release checklist`

## Pull request workflow

1. Rebase or merge latest `main` into your branch.
2. Run local validation.
3. Open a pull request into `main`.
4. Wait for CI to pass before merging.

Local validation commands:

```powershell
.venv\Scripts\python.exe -m py_compile src\garmin_obsidian_sync\config.py src\garmin_obsidian_sync\garmin_connect_sync.py src\garmin_obsidian_sync\exporter.py src\garmin_obsidian_sync\cli.py src\garmin_obsidian_sync\webapp.py
garmin-obsidian-sync --help
cd frontend
npm run build
```

If your change touches Garmin sync or Obsidian export, include a short note in the PR describing what you tested locally.

## Merge strategy

- Prefer `Squash and merge` for feature branches to keep `main` readable.
- Keep the PR title in a format that can serve as the squash commit message.

## Secrets and local files

- Never commit `config.local.json`.
- Never commit Garmin credentials, tokens, or generated personal data.
- Keep exported data and runtime files local only unless you explicitly want versioned samples.

## Suggested GitHub settings

In repository settings, enable these protections for `main`:

- Require a pull request before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict direct pushes to `main`
