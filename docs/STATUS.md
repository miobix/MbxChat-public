# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 7 (the agent) merged (PR #13, 2026-11-24). Next: unit 8 (learner memory,
SPEC §8) on `unit-8-memory` from a fresh `main`; it ends cycle 2 (hardening pass, doc roll-up). Decisions: DECISIONS
"2026-11-23 Unit 7 plan", "2026-11-23 Unit 7 build", "2026-11-24 Unit 7: the agent".

## Unit 7 in one paragraph
Capture runs in agent mode by default (`CAPTURE_MODE`): the agent (`mbxchat/agent.py`, read-only
tools on the `mcp` service) decides word or sentence. Words go to a fixed `word_lookup` (krdict,
root fallback, examples that contain the word) and a card into `ANKI_WORD_DECK`; sentences run
the unit 3 workflow chain unchanged. In a session, free text is routed (answer / capture /
question). MbxRead is opt-in via `MBXREAD_URL`. Phone check passed 2026-11-24.

## Later
- **README note for unit 11:** MbxRead material is used when `MBXREAD_URL` is set and ignored
  when not; the author shares MbxRead's Ollama. Also CPU vs GPU numbers (same host, same
  grader set of 66, DECISIONS 2026-11-24 "Unit 7 wrap-up"): gemma4:e4b grading median 11.0 s
  on CPU vs 1.4 s on GPU; decode ~9 vs 159-192 tokens/s.
- **Open question (user): spacing slips.** `grade()` compares with spaces stripped, so a
  spacing-only fix (집에가서 → 집에 가서) keeps the verdict `correct`.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions.
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **End of cycle 2 (after unit 8):** run the two imported wishes through capture, then drop the
  `wish` kind (schema check, SPEC §5, importer notes); then the `hardening-pass` skill.
- **Hardening proposals, not done:** retention for LangGraph checkpoint tables, Phoenix traces
  and `krdict_cache` (all small; revisit at unit 9). Backups sit on the same disk as the
  database; copying them off the machine is the user's call.
- **Skill proposal, on hold:** `capture-smoke` (scratch-DB traced capture). Skills in use:
  CLAUDE.md, "Skills" (`lockfile-recompile` added 2026-11-24).

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose (`restart: unless-stopped`): `bot` (health `127.0.0.1:8005`), `mcp` (tool server on
  the bot's image, compose network only, `mcp:8006/mcp`), `db` (`127.0.0.1:5434`), `phoenix`
  (`127.0.0.1:6006`, auth off), `backup` (nightly `pg_dump` to `./backups`, newest 14; restore
  in README). **Rebuild with plain `docker compose up -d --build`**: naming only `bot` leaves
  `mcp` on old code. Token and allowed user ID in `.env`; missing either → exit with what's
  missing.
- Config in `.env`: `KRDICT_API_KEY` (set), `MBXREAD_URL=http://host.docker.internal:8002`
  (set; MbxRead's own `.env` `ALLOWED_HOSTS` includes `host.docker.internal`), `CAPTURE_MODE`
  (unset = agent), `ANKI_WORD_DECK` (unset = `MbxChat::Words`).
- Practice (SPEC §7d): `/practice`, `/stop`, `/pause`; pings in `PRACTICE_TZ`. Tables `session`,
  `prompt`, `drill`, `setting`. Routing of free text in a session: SPEC §7e.
- `/` menu: set at startup for the allowed chat only. `practice`, `stop`, `pause`, `help`,
  `grammar`, `queue`, `demo`. Groups disabled in BotFather. `/demo` is a UI preview; remove it
  once real flows replace it.
- Capture: workflow (SPEC §7c) draft → lookup → critic → chunks (~3-6 s on GPU), one card per
  chunk into `chunk`; agent mode (SPEC §7e) adds the word path into `word_card`. A pending ✏️
  edit lives in memory (a restart forgets it). Model `gemma4:e4b` (ID `dc35e8d9c606`, checked at
  startup) on MbxRead's Ollama :11434, GPU; the only model kept after 6b.
- Anki (SPEC §7): chunks → deck `MbxChat`, note type `MbxChat Chunk`; words → `ANKI_WORD_DECK`,
  note type `MbxChat Word` (created once; template changes in code do not reach an existing
  note type). AnkiConnect at `host.docker.internal:8765`; both outboxes retried every 60 s.
- krdict: `krdict_cache` table, `krdict_last` / `krdict_blocked_until` in `setting`. Live use so
  far this unit: a handful of requests (최적화, 최적, 마감일, a few drafts' words).
- Lockfile: `pip-compile` on Windows pins `pywin32` (pulled by `mcp`) for every platform; re-add
  `; sys_platform == "win32"` to its line in `requirements.txt` or the image build fails.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals: on the host (`requirements-eval.txt`, `PYTHONUTF8=1` when output goes to a file):
  `python -m evals.grader_eval MODEL...`, `python -m evals.capture_side_by_side MODEL...`,
  `python -m evals.tool_calling MODEL...`. Needing the `mcp` service (no host port):
  `docker compose run --rm --no-deps -v "$(pwd -W)/evals:/app/evals" bot python -m evals.capture_ab`
  (Git Bash; a relative `-v ./evals` mount came up empty). Results in `evals/results/`.
- Tests: 136 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model, krdict HTTP and MbxRead faked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002 .venv/Scripts/python -m mbxchat.importer`
  on the host (refuses an answer with under half the stored count). Nothing reads MbxWrite: its
  wishes were imported once and the database (and its backups) is their only copy. Provenance
  in `docs/DATA.md`. Known grammar in `known_grammar`; basics seeded on the first import only.
