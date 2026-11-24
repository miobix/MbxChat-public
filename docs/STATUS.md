# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** cycle 2 (units 5-8) closed with unit 8 (learner memory, SPEC §7f) on `unit-8-memory`,
PR pending. Next: unit 9 (monitoring, SPEC §8) from a fresh `main`. Decisions: DECISIONS
"2026-11-24 Unit 8 plan", "2026-11-24 Unit 8: learner memory", "2026-11-24 Hardening pass, cycle 2".

## Cycle 2 in one paragraph
Practice (unit 5) serves grammar and translate prompts, grades them with `gemma4:e4b` (chosen in
6b on a labeled set of 66, GPU), and resurfaces grammar points on a 3/10/30/90-day ladder.
Capture runs as a tool-calling agent (unit 7): words get a krdict card, sentences run the unit 3
chain. Unit 8 made practice varied (captures never prompted back, pool sentences used once, then
generated ones) and gave it a memory: mistakes are tagged by diffing each answer against its
correction, and a mistake repeated twice steers at most one prompt in three (🎯 line, `/weak`).

## Later
- **Revisit memory with more data (user):** thresholds (2 in 30 days, one in three steered),
  tagging quality (`other` share, the 습니다 → 어요 register case), and an agent choosing the next
  drill once there are a few hundred graded answers.
- **Long multi-clause sentences** (conditionals, counterfactuals) are what writing practice
  should push toward; a candidate for generated prompts once memory has data.
- **README note for unit 11:** MbxRead material is used when `MBXREAD_URL` is set and ignored
  when not; the author shares MbxRead's Ollama. CPU vs GPU numbers: DECISIONS 2026-11-24
  "Unit 7 wrap-up".
- **Open question (user): spacing slips.** `grade()` compares with spaces stripped, so a
  spacing-only fix keeps the verdict `correct`. Spacing slips are now recorded in `mistake`.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions.
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **Hardening proposals, not done:** retention for checkpoints, Phoenix traces and
  `krdict_cache` (all small; revisit at unit 9). Backups sit on the same disk as the database;
  copying them off the machine is the user's call.
- **Skill proposal, on hold:** `capture-smoke` (scratch-DB traced capture).

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose (`restart: unless-stopped`): `bot` (health `127.0.0.1:8005`), `mcp` (tool server on
  the bot's image, compose network only, `mcp:8006/mcp`), `db` (`127.0.0.1:5434`, user and
  database `mbxchat`), `phoenix` (`127.0.0.1:6006`, auth off), `backup` (`pg_dump` every 24 h
  from container start to `./backups`, newest 14; restore in README). **Rebuild with plain
  `docker compose up -d --build`**: naming only `bot` leaves `mcp` on old code. Rebuilds leave
  dangling images: `docker image prune -f --filter label=com.docker.compose.project=mbxchat`.
- Config in `.env`: `KRDICT_API_KEY` (set), `MBXREAD_URL=http://host.docker.internal:8002`
  (set), `CAPTURE_MODE` (unset = agent), `ANKI_WORD_DECK` (unset = `MbxChat::Words`).
- Practice (SPEC §7d, §7f): `/practice`, `/stop`, `/pause`, `/weak`; pings in `PRACTICE_TZ`.
  Tables `session`, `prompt` (`pick` new/due/weak, `focus`), `drill` (grammar points; old
  capture and sentence rows ignored), `mistake`, `setting`. Free-text routing: SPEC §7e.
- `/` menu: set at startup for the allowed chat only. `/demo` is a UI preview; remove it once
  real flows replace it.
- Capture: workflow (SPEC §7c) and agent (SPEC §7e, default). A pending ✏️ edit lives in memory
  (a restart forgets it). Model `gemma4:e4b` (ID `dc35e8d9c606`, checked at startup) on
  MbxRead's Ollama :11434, GPU.
- Anki (SPEC §7): chunks → deck `MbxChat`, note type `MbxChat Chunk`; words →
  `ANKI_WORD_DECK`, note type `MbxChat Word` (template changes in code do not reach an existing
  note type). AnkiConnect at `host.docker.internal:8765`; both outboxes retried every 60 s.
- krdict: `krdict_cache` table, `krdict_last` / `krdict_blocked_until` in `setting`.
- Lockfiles: use the `lockfile-recompile` skill (keeps the `pywin32` Windows marker).
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals: on the host (`requirements-eval.txt`, `PYTHONUTF8=1` when output goes to a file):
  `evals.grader_eval`, `evals.capture_side_by_side`, `evals.tool_calling`; needing `mcp`: the
  `eval-in-container` skill (`evals.capture_ab`). Results in `evals/results/`.
- Tests: 142 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model, krdict HTTP and MbxRead faked.
- Content: one `item` table (kinds grammar, sentence, word, term). Public pools (`data/`) are
  upserted at every bot start; MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002
  .venv/Scripts/python -m mbxchat.importer` on the host (refuses an answer with under half the
  stored count). Nothing reads MbxWrite. Provenance in `docs/DATA.md`. Known grammar in
  `known_grammar`; basics seeded on the first import only.
