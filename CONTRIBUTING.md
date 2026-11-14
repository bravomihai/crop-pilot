# Contributing - NASA Space Apps 2026

## Branches

| Branch | Description | 
| ----- | ----- | 
| `main` | Stable, working code (requires review to merge) | 
| `mihai` | Mihai's branch | 
| `andrei` | Andrei's branch | 
| `tudor` | Tudor's branch | 
| `alexia` | Alexia's branch | 
| `maria` | Maria's branch | 

## Initial Setup

```bash
git clone https://github.com/bravomihai/nasa-space-apps-2026.git
cd nasa-space-apps-2026
```

If your branch does not exist yet, create it (e.g., for `andrei`):

```bash
git checkout -b andrei        # creates the local branch and switches to it
git push -u origin andrei     # pushes it to GitHub for the first time
```

If the branch already exists (created previously):

```bash
git checkout andrei
```

## Daily Workflow

### 1. Before working - update your branch:

```bash
git checkout main
git pull origin main
git checkout andrei
git merge main
```

### 2. Work and save your progress:

```bash
git add .
git commit -m "add data processing function"
git push origin andrei
```

### 3. When the code works - integrate it into `main` (with Review):

Do not run `git push origin main` directly. Merging into `main` is done only via a **Pull Request (PR)** on GitHub:

1. Make sure you have run `git push origin andrei` with your latest changes.
2. Go to GitHub (`bravomihai/nasa-space-apps-2026`) and open a **Pull Request** from your branch (`andrei`) into `main`.
3. At least one teammate must **Review & Approve** the PR.
4. Once approved, click **Merge pull request** on GitHub.

## Visual Summary

```text
main    ──────────●──────────────●──────  (merge only via PR + Review)
                 ↑ (PR)           ↑ (PR)
andrei  ──●───●──┘      ●────●────┘
tudor        ────●───●─────────────●────
```

## Rules

* Do not work directly on `main` and do not push directly to `main`.
* Pull from `main` before opening a PR to avoid merge conflicts.
* Test your code before requesting a review for `main`.
* At least 1 approval (review) from a teammate is required before merging into `main`.
* Write clear commit messages, not `"wip"`.

## Merge Conflicts

If conflicts occur when running `git merge main`, Git will display the differences like this:

```text
<<<<<<< andrei
your code
=======
code from main
>>>>>>> main
```

Choose what to keep, delete the `<<<<<<<`, `=======`, and `>>>>>>>` lines, then run:

```bash
git add .
git commit -m "resolve merge conflict"
git push origin andrei
```

## Useful Commands

| Command | What it does | 
| ----- | ----- | 
| `git status` | shows modified files | 
| `git log --oneline` | shows commit history | 
| `git diff` | shows what has changed | 
| `git fetch origin` | checks for updates on GitHub without pulling them | 
