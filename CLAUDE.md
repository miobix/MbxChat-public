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

## Rules
1. **One unit = one branch + one PR**, green CI, docs updated. Finish units as local commits;
   push and open the PR only when the user asks.
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
