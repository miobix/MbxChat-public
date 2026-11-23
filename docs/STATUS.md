# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 6b merged (PR #12). Unit 7 (the agent) planned on `unit-7-agent`: SPEC §7e,
DECISIONS "2026-11-23 Unit 7 plan".

## Next
- **Unit 7 build order** (each step tested before the next):
  1. Done: `MBXREAD_URL` opt-in (empty default = no MbxRead calls, no notes; importer says
     "skipped, MBXREAD_URL not set"). The author's `.env` sets it; live bot reaches MbxRead.
  2. Own krdict client: paced 1 request / 3 s, cached in Postgres, stop at the first failure.
     Needs a krdict Open API key from the user (`KRDICT_API_KEY` in `.env`).
  3. `mcp` service: read-only tools `krdict_lookup`, `library_examples` (only with
     `MBXREAD_URL`), `known_items`; the bot loads them through LangChain's MCP adapters. Pin it.
  4. Capture agent behind `CAPTURE_MODE` (default `workflow`): kind + Korean by the agent,
     grounding (dictionary check, library examples) as fixed steps; sentence path hands off to
     the unit 3 critic → chunks → review → save.
  5. Word path: `MbxChat Word` note type, `ANKI_WORD_DECK` (default `MbxChat::Words`), outbox
     rows on the chunk push loop, `findNotes` dedupe, `[✅ Approve] [⏭ Skip]` card.
  6. Session routing: one structured call (answer / capture / question) before grading.
  7. Eval: agent vs workflow on the 10 side-by-side prompts + word prompts (user judges), calls
     and latency; rerun `evals/tool_calling.py` with real tools. Pick `CAPTURE_MODE` default.
  8. Phone check, docs, PR.
- **README note for unit 11:** MbxRead material (library examples, saved terms) is used when
  `MBXREAD_URL` is set and ignored when not; the author shares MbxRead's Ollama.
- **Open question (user): spacing slips.** `grade()` compares with spaces stripped, so a
  spacing-only fix (집에가서 → 집에 가서) keeps the verdict `correct`. Decide whether spacing
  should count as minor; a change would make the three spacing items in the set score.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions. Spec it as its own project.
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **End of cycle 2 (after unit 8):** run the two imported wishes through capture, then drop the
  `wish` kind (schema check, SPEC §5, importer notes). This app processes wishes at once; it
  does not store them.
- **Cycle 2 boundary:** after unit 8 merges, run the `hardening-pass` skill.
- **Hardening proposals, not done:** retention for LangGraph checkpoint tables and Phoenix
  traces (both tiny today; revisit at unit 9 monitoring). Backups sit on the same disk as the
  database; copying them off the machine is the user's call.
- **Skill proposal, on hold:** `capture-smoke` (`.claude/skills/`), scratch-DB traced capture.
  The user reconsiders it if the pattern repeats. Skills in use: CLAUDE.md, "Skills".

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose runs everything (`docker compose up -d --build`, `restart: unless-stopped`): `bot`
  (health `127.0.0.1:8005`), `db` (`127.0.0.1:5434`; 5432/5433 are taken), `phoenix`
  (`127.0.0.1:6006`, auth off, localhost only), `backup` (nightly `pg_dump` to `./backups`,
  newest 14; restore in README). Token and allowed user ID in `.env`; missing either → exit
  with what's missing.
- Practice (SPEC §7d): `/practice`, `/stop`, `/pause`; pings in `PRACTICE_TZ` (set in `.env`).
  Tables `session`, `prompt`, `drill`, `setting`.
- `/` menu: set at startup for the allowed chat only. `practice`, `stop`, `pause`, `help`,
  `grammar`, `queue`, `demo`. Groups
  disabled in BotFather. `/demo` is a UI preview; remove it once real flows replace it.
- Capture (SPEC §7c): ➕ runs draft → lookup → critic → chunks (~10 s on GPU), then one card
  per chunk; approved and edited chunks land in `chunk`. A pending ✏️ edit lives in memory (a
  restart forgets it). Uses MbxRead when `MBXREAD_URL` is set (krdict via `/api/dict` until
  unit 7, `/api/usage`); MbxRead's Ollama :11434 (`gemma4:e4b`, ID `dc35e8d9c606`, checked at
  startup with a warning; on GPU since the Docker Desktop update; the only model kept after 6b).
- Anki (SPEC §7): deck `MbxChat`, note type `MbxChat Chunk` (created once; template changes in
  code do not reach an existing note type), AnkiConnect at `host.docker.internal:8765`. `chunk`
  is the outbox; retried every 60 s.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals (host only, `requirements-eval.txt`): `python -m evals.grader_eval MODEL...` (also
  `dadeum`, `<model>+dadeum`) and `python -m evals.capture_side_by_side MODEL...` (set
  `MBXREAD_URL=http://127.0.0.1:8002` in the shell for lookups). Results in `evals/results/`. Set `PYTHONUTF8=1` when output goes to a file.
- Tests: 95 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model and MbxRead faked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002 .venv/Scripts/python -m mbxchat.importer`
  on the host (refuses an answer
  with under half the stored count). Nothing reads MbxWrite: its wishes were imported once and
  the database (and its backups) is their only copy. Provenance in `docs/DATA.md`. Known grammar
  in `known_grammar`; basics seeded on the first import only.
- MbxRead is reached at `MBXREAD_URL` from `.env` (`host.docker.internal:8002`; compose no longer
  sets it); MbxRead's `.env` `ALLOWED_HOSTS` includes `host.docker.internal`.
