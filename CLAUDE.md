# MbxChat

Telegram bot for practising written Korean, built as a LangGraph agent. Built in public.

Read `docs/STATUS.md` first every session. Also read `personal_notes/` (untracked) every
session, if present.

## Docs
- `docs/STATUS.md`: living state. Rewrite in place, prune finished work.
- `docs/SPEC.md`: the contract (what the app is, the stack, the units). Change it in the same
  commit as any deviation.
- `docs/DECISIONS.md`: append-only log of what was decided and why. Never rewrite.
- `docs/DATA.md` (from unit 2): provenance and licence of every content source.

## Skills (`.claude/skills/`)
- `finish-unit`: tests, docs, commit, PR, CI watch and report; after a merge, the next branch
  from a fresh `main`. Reach for it whenever a unit's code is done or the user reports a merge.
- Cycle boundaries (units 4, 8, 11) also use the user-level `hardening-pass` skill.

## Rules
1. **One unit = one branch + one PR**, green CI, docs updated. When a unit is done, push it,
   open the PR, watch CI and report. **The user merges on GitHub**; never merge yourself.
2. **No personal data in the repo**: captured phrases, wishes, saved terms, learner memory,
   machine names, Telegram IDs and tokens stay in the local database or `.env`.
3. **External APIs:** krdict one request per 3 s, cached, never retried in a burst; stop at the
   first failure and tell the user. No paid model APIs.
4. **Pin versions** (use the `pin-versions` skill): images by digest, actions by SHA, model
   weights by revision.
5. **Tests pass offline**: mock Telegram, krdict, AnkiConnect, MbxRead and model HTTP; a temp
   Postgres database per test. Use `127.0.0.1`, never `localhost`, in URLs on Windows.
6. LangGraph nodes re-run from their start after an interrupt: side effects before an
   `interrupt()` must be idempotent.
