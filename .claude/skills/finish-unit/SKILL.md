---
name: finish-unit
description: Close an MbxChat unit - full tests, docs updated (STATUS rewritten in place, DECISIONS appended, SPEC changed with any deviation), one commit, push, open the PR, watch CI and report; after the user merges, start the next branch from a freshly pulled main. Use when a unit's code is done, or the user says "finish the unit", "open the PR", or reports a merge.
---

# finish-unit

The user merges every PR on GitHub. Never run `gh pr merge` or merge to `main` locally.

## Before the PR

1. `docker compose up -d --wait db`, then `.venv/Scripts/python -m pytest tests -q`: all green.
   Note the count for STATUS.
2. If the unit runs in the daily bot: `docker compose up -d --build` (no service name: `bot` and
   `mcp` share the image, and naming only `bot` leaves `mcp` on old code), then read
   `docker compose logs --since 2m bot mcp` for warnings.
3. Docs, in the same commit:
   - `docs/STATUS.md`: rewrite Phase and Next; prune finished work; update Facts and the test count.
   - `docs/DECISIONS.md`: a dated `## <date> Unit N: <name>` section, appended, never rewritten.
   - `docs/SPEC.md`: any deviation from the contract, changed now.
   - Reread new prose: nothing personal (CLAUDE.md rule 2 and the user's global rule).
4. Multi-anchor edits go through the `safe-edit` skill (files are CRLF in the working tree).

## PR

```bash
git add -A && git commit -F - <<'EOF'   # message + the Co-Authored-By line from the session
git push -u origin <branch>
gh pr create --base main --title "Unit N: <name>" --body "..."   # ends with the Claude Code line
sleep 15; gh pr checks <n> --watch
```

`gh pr checks` right after creating can report "no checks"; wait and rerun. Report CI with the
job results. If a phone check is still pending, say exactly what the user should do.

## After the user's check or merge

- Check the PR state first (`gh pr view <n> --json state`): the user merges fast. If merged, any
  code fix goes on a new branch from a fresh `main`, not the old one. Docs-only upkeep (STATUS after the
  merge, a verification note) never gets its own PR: it is the first commit on the next unit's branch.
- Next unit: `git checkout main && git pull && git checkout -b unit-<n>-<slug>`.
- Units 4, 8 and 11 end a cycle: run the `hardening-pass` skill and roll up the docs.
- Then do whatever `personal_notes/` asks at the end of a unit, if present.
