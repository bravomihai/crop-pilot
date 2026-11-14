# Contributing to NASA Space Apps 2026

## Team Branches

Work only on your personal branch:

* **Mihai:** `mihai`
* **Andrei:** `andrei`
* **Tudor:** `tudor`
* **Alexia:** `alexia`
* **Maria:** `maria`

## First-Time Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/bravomihai/nasa-space-apps-2026.git
   cd nasa-space-apps-2026
   ```

2. Switch to your branch (or create it from `main` if it doesn't exist yet):
   ```bash
   git checkout main
   git pull origin main
   git checkout -b <your-branch-name>
   git push -u origin <your-branch-name>
   ```

## How to Pull & Push Correctly

### 1. Before you start working (Pull latest changes)
Always sync your branch with `main` before writing new code:
```bash
git checkout main
git pull origin main
git checkout <your-branch-name>
git merge main
```

### 2. When you finish a task (Push your changes)
Save and push your work to your own branch:
```bash
git add .
git commit -m "short description of what you changed"
git push origin <your-branch-name>
```

## Merging into `main` (Review Required)

* **Do not push directly to `main`.**
* Open a **Pull Request (PR)** on GitHub from `<your-branch-name>` into `main`.
* **At least one teammate must review and approve** the Pull Request before it can be merged into `main`.
