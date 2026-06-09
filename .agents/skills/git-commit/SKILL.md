---
name: git-commit
description: 'Conventional commit creator with auto-staging and message generation.'
license: MIT
allowed-tools: Bash
---

# Git Commit

1. **Context:** `git log -n 5` to match repo style.

2. **Review:** `git status` and `git diff`.

3. **Stage & Group:** If many files changed, group them into **multiple logical commits** (`git add <files>`). No secrets.

4. **Message:** ALL commits should be multiline. (No `!` for breaking changes because we are still in early alpha). Format:

   ```text
    <type>(<scope>): <title>

    <body>
   ```

   where `<title>` ≤ 72 characters (ideal ≤ 50) and `body` wrap at 72 characters. The best commit messages help someone six months later answer "Why was this change made?".

5. **Commit:** Execute using heredoc:

   ```bash
   git commit -m "$(cat <<'EOF'
   <message here>
   EOF
   )"
   ```

6. **Iterate:** Repeat steps 3-5 until all logical groups are committed.

7. **Safety:** No `--force`, `reset --hard`, config changes, or `--no-verify`.
