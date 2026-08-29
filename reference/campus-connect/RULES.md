# Source Control Playbook

## Start of every day
First thing, before any code: pull a fresh `dev` so you're building on what the team already merged. Daily, no exceptions.

## How the repo is laid out
Three tiers, top to bottom:
- `main` (locked) only release-ready, deployable code
- `dev` the staging area where vetted features get combined
- `feature/<who>-<what>` short-lived branches for what you're building now (e.g. `feature/shrestha-checkout-api`)

Code flows up: `feature/...` → `dev` → `main`.

## Labeling your commits
Tag every message with its purpose:
- `feat:` something new → `feat: add email format check on signup`
- `fix:` a bug squashed → `fix: correct misaligned header menu`
- `refactor:` cleanup, no behavior change → `refactor: simplify query layer`

## Your everyday loop
1. Pull the newest `dev`: `git pull origin dev`
2. Branch off for the task: `git checkout -b feature/name-task`
3. Commit progress in small, sensible chunks
4. Push your branch: `git push origin your-branch`
5. When the feature's done, open a Pull Request into `dev`

## Rules that don't bend
- Everything ships through a Pull Request. Pushing straight to `main` or `dev` is banned.
- Never rewrite shared history with `git push --force`
- The morning `dev` sync is mandatory, not optional

## When you hit a wall
- Got a question? Comment right on the issue or PR.
- Merge conflict? Fix it locally first. Escalate only if truly stuck.
