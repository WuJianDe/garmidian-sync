# Git Workflow

This repository uses a simple trunk-based workflow with a protected `main` branch.

## Day-to-day flow

1. Update local `main`

```powershell
git checkout main
git pull origin main
```

2. Create a work branch

```powershell
git checkout -b feature/my-change
```

3. Make changes and commit

```powershell
git add .
git commit -m "feat: describe the change"
```

4. Push branch

```powershell
git push -u origin feature/my-change
```

5. Open PR into `main`

6. After CI passes, squash-merge the PR

7. Clean up local branch

```powershell
git checkout main
git pull origin main
git branch -d feature/my-change
```

## Hotfix flow

For urgent fixes:

```powershell
git checkout main
git pull origin main
git checkout -b fix/critical-export-bug
```

Open a PR as usual. Avoid pushing directly to `main`.

## Release habit

For now, use `main` as the release branch.

Recommended release checklist:

- CI green on `main`
- README updated if setup or commands changed
- Config example updated if config schema changed
- Export format changes documented if Obsidian structure changed

