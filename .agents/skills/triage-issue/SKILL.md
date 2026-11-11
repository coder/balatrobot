---
name: triage-issue
description: Triage and reproduce GitHub issues for the coder/balatrobot repo. Fetches issue data, downloads attachments, creates a branch, reproduces the bug, and generates an HTML investigation report. Use when the user says "/triage-issue NNN" or asks to reproduce a specific issue by number.
---

# Triage Issue

Reproduce and investigate a GitHub issue end-to-end, producing an HTML report.

## Quick start

User provides a GitHub issue URL. Extract the issue number and run the full workflow below.

## Workflow

### 1. Fetch & download

```bash
mkdir -p /tmp/balatrobot/issues/NNN
gh issue view NNN --repo coder/balatrobot --json title,body,comments,labels,state \
  | tee /tmp/balatrobot/issues/NNN/issue.json
```

Extract attachment URLs from body + comments and download:
```bash
gh issue view NNN --repo coder/balatrobot --json body,comments -q '.body, (.comments[].body)' \
  | grep -oE 'https://github.com/user-attachments/files/[^ )]+' \
  | xargs -I{} curl -sLo /tmp/balatrobot/issues/NNN/$(basename {}) '{}'
```

### 2. Read before executing

**Before running anything**, read all downloaded files:
- **`script.py`** — reproduction script. Read fully before running.
- **`*.req.jsonl`** — replayable via `balatrobot api --requests`.
- **`*.res.jsonl`** — response log for comparison.
- **`*.log`** — Balatro log output for error context.

Choose reproduction method: `script.py` if present (adapt port), else replay `.req.jsonl`.

### 3. Create branch

Derive prefix from issue title (`fix(...)` → `fix/`, `feat(...)` → `feat/`, etc., fallback `fix/`):
```bash
git checkout <current-active-branch>
git checkout -b <prefix>/issue-NNN
```

### 4. Reproduce

```bash
balatrobot serve --render headless --settings turbo --debug
```

Wait for ready, then reproduce using the chosen method. Run **≥3 times** to confirm consistency.

### 5. Report & cleanup

Generate HTML report at `/tmp/balatrobot/issues/NNN/report.html`. See [REFERENCE.md](REFERENCE.md) for template. Must include: issue title, verdict badge (`REPRODUCED`/`ALREADY FIXED`/`NEEDS MANUAL REVIEW`), summary, reproduction steps, results table, analysis, conclusion.

Then:
- `balatrobot stop`
- If already fixed → delete branch, switch back.
- If reproducible → keep branch.
- `open /tmp/balatrobot/issues/NNN/report.html`

## Checklist

Before reporting done, verify:
- [ ] Issue data fetched and saved to `/tmp/balatrobot/issues/NNN/`
- [ ] All attachments downloaded
- [ ] Attachments read and understood before execution
- [ ] Branch created from active branch
- [ ] Issue reproduced (or confirmed already fixed) with ≥3 runs
- [ ] HTML report generated at `/tmp/balatrobot/issues/NNN/report.html`
- [ ] Report opened in browser
- [ ] Server stopped, branch cleaned up if no fix needed
