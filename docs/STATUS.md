# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** cycle 1 (units 0-4) done and verified on the phone; hardening pass and roll-up on
`cycle-1-hardening`. Next: unit 5 (practice loop).

## Next
- **Unit 5:** practice loop (SPEC §8), plus capture context: text after `//` is the situation,
  stored on `capture` and shown to draft, critic and chunks.
- **Hardening proposals, not done:** retention for LangGraph checkpoint tables and Phoenix
  traces (both tiny today; revisit at unit 9 monitoring). Backups sit on the same disk as the
  database; copying them off the machine is the user's call.
- **Skill proposal, on hold:** `capture-smoke` (`.claude/skills/`), scratch-DB traced capture.
  The user reconsiders it if the pattern repeats. Skills in use: CLAUDE.md, "Skills".
- Capture quality (critic wording, chunk choice, register slips like a polite draft without 요) is
  for the unit 6 eval, not prompt tweaks by feel.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose runs everything (`docker compose up -d --build`, `restart: unless-stopped`): `bot`
  (health `127.0.0.1:8005`), `db` (`127.0.0.1:5434`; 5432/5433 are taken), `phoenix`
  (`127.0.0.1:6006`, auth off, localhost only), `backup` (nightly `pg_dump` to `./backups`,
  newest 14; restore in README). Token and allowed user ID in `.env`; missing either → exit
  with what's missing.
- `/` menu: set at startup for the allowed chat only. `help`, `grammar`, `queue`, `demo`. Groups
  disabled in BotFather. `/demo` is a UI preview; remove it once real flows replace it.
- Capture (SPEC §7c): ➕ runs draft → lookup → critic → chunks (~30-50 s on CPU), then one card
  per chunk; approved and edited chunks land in `chunk`. A pending ✏️ edit lives in memory (a
  restart forgets it). Needs MbxRead's stack: API :8002 (krdict via `/api/dict`, `/api/usage`)
  and its Ollama :11434 (`gemma4:e4b`, ID `dc35e8d9c606`, checked at startup with a warning).
- Anki (SPEC §7): deck `MbxChat`, note type `MbxChat Chunk` (created once; template changes in
  code do not reach an existing note type), AnkiConnect at `host.docker.internal:8765`. `chunk`
  is the outbox; retried every 60 s.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Tests: 74 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model and MbxRead faked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `.venv/Scripts/python -m mbxchat.importer` on the host (refuses an answer
  with under half the stored count). Nothing reads MbxWrite: its wishes were imported once and
  the database (and its backups) is their only copy. Provenance in `docs/DATA.md`. Known grammar
  in `known_grammar`; basics seeded on the first import only.
- MbxRead is reached at `host.docker.internal:8002`; its `.env` `ALLOWED_HOSTS` includes
  `host.docker.internal`.
