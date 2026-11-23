# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 6b merged (PR #12). Unit 7 (the agent) planned on `unit-7-agent`: SPEC §7e,
DECISIONS "2026-11-23 Unit 7 plan".

## Next
- **Unit 7 build order** (each step tested before the next):
  1. Done: `MBXREAD_URL` opt-in (empty default = no MbxRead calls, no notes; importer says
     "skipped, MBXREAD_URL not set"). The author's `.env` sets it; live bot reaches MbxRead.
  2. Done: own krdict client `mbxchat/krdict.py` (cache table `krdict_cache`, 3 s gap, 30 min
     pause after a failure stored in `setting`, survives restarts; `search` = 1 request,
     `examples` = 1 more, only when needed). Live: key in `.env`, one request (최적화 → 0
     entries: not in the learners' dictionary); parsing checked on MbxRead's cached answers.
  3. Done: `mcp` compose service (`mbxchat/mcp_server.py`, the bot's image, streamable HTTP on
     `mcp:8006/mcp`, no host port). Tools offered only when configured: `krdict_lookup` (key),
     `library_examples` (`MBXREAD_URL`), `known_items` (always). Live: the bot lists all three
     over HTTP and calls them. krdict's 3 s gap now holds across processes (Postgres advisory
     lock + `krdict_last` in `setting`). Deps `mcp==1.30.0`, `langchain-mcp-adapters==0.3.2`.
  4. Done: `mbxchat/agent.py` behind `CAPTURE_MODE` (default `workflow`, live bot unchanged).
     Agent node (MCP tools + submit_word / submit_sentence, max 6 steps, a bad submit goes back
     to the model) → sentence: unit 3 chain from `lookup`; word: `word_lookup` (krdict, one root
     fallback 최적화 → 최적, examples library → krdict → model, marked). Live, nodes called
     directly (no capture rows): word 16 s, 1 tool call, root found, 1 krdict request; sentence
     6 s, 0 tool calls. **Library examples for 최적화 were transcript fragments** ("해서 어떻게
     최적화를 좀 달할 수"): decide in step 5 whether cards prefer krdict/model examples.
  5. Done: word cards. `word_lookup` → card `[✅ Approve] [⏭ Skip]` (interrupt) → `word_save`
     into `word_card` (outbox) → Anki `MbxChat Word` in `ANKI_WORD_DECK` (default
     `MbxChat::Words`); a word already in that deck under any note type with a Korean field is
     marked duplicate, not added. Examples: full-sentence library hits, else krdict, else model
     (marked). `capture.kind = 'word'` keeps word captures out of practice. Not seen live yet:
     the phone check (step 8) is the first real card.
  6. Done: session routing (`practice.route`, all capture modes). Mostly-Hangul = answer, no
     call; else one call. Non-answers get `[➕ Capture] [💬 Answer it]` + `[✍️ Grade it as my
     answer]`, ordered by the guess. Live: 5 messages, 1 miss (a capture guessed as question),
     0.2-0.3 s per call warm; "Answer it" 0.5 s. Convention (user): in a session, Korean
     phrases are answers, captures and questions are English; a single Korean word (no space)
     is offered for capture, no call. A Korean question would be graded (by design).
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
  newest 14; restore in README), `mcp` (tool server on the bot's image: rebuild with plain
  `docker compose up -d --build`, never `... bot` alone, or `mcp` keeps old code). Token and allowed user ID in `.env`; missing either → exit
  with what's missing.
- Practice (SPEC §7d): `/practice`, `/stop`, `/pause`; pings in `PRACTICE_TZ` (set in `.env`).
  Tables `session`, `prompt`, `drill`, `setting`.
- `/` menu: set at startup for the allowed chat only. `practice`, `stop`, `pause`, `help`,
  `grammar`, `queue`, `demo`. Groups
  disabled in BotFather. `/demo` is a UI preview; remove it once real flows replace it.
- Capture (SPEC §7c): ➕ runs draft → lookup → critic → chunks (~10 s on GPU), then one card
  per chunk; approved and edited chunks land in `chunk`. A pending ✏️ edit lives in memory (a
  restart forgets it). Uses MbxRead when `MBXREAD_URL` is set (`/api/usage`); krdict through
  MbxChat's own client when `KRDICT_API_KEY` is set; MbxRead's Ollama :11434 (`gemma4:e4b`, ID `dc35e8d9c606`, checked at
  startup with a warning; on GPU since the Docker Desktop update; the only model kept after 6b).
- Anki (SPEC §7): deck `MbxChat`, note type `MbxChat Chunk` (created once; template changes in
  code do not reach an existing note type), AnkiConnect at `host.docker.internal:8765`. `chunk`
  is the outbox; retried every 60 s.
- Lockfile: `pip-compile` on Windows pins `pywin32` (pulled by `mcp`) for every platform; re-add
  `; sys_platform == "win32"` to its line in `requirements.txt` or the image build fails.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals (host only, `requirements-eval.txt`): `python -m evals.grader_eval MODEL...` (also
  `dadeum`, `<model>+dadeum`) and `python -m evals.capture_side_by_side MODEL...` (set
  `MBXREAD_URL=http://127.0.0.1:8002` in the shell for lookups). Results in `evals/results/`. Set `PYTHONUTF8=1` when output goes to a file.
- Tests: 130 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model and MbxRead faked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002 .venv/Scripts/python -m mbxchat.importer`
  on the host (refuses an answer
  with under half the stored count). Nothing reads MbxWrite: its wishes were imported once and
  the database (and its backups) is their only copy. Provenance in `docs/DATA.md`. Known grammar
  in `known_grammar`; basics seeded on the first import only.
- MbxRead is reached at `MBXREAD_URL` from `.env` (`host.docker.internal:8002`; compose no longer
  sets it); MbxRead's `.env` `ALLOWED_HOSTS` includes `host.docker.internal`.
