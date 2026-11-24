# DECISIONS (append-only log: never rewrite, never compress)

## 2026-11-22 Scope and stack
- **Telegram bot, long polling:** the phone's chat app is the UI, nothing listens on a public port, and a chat gives practice a session shape.
- **LangGraph** for orchestration: `interrupt()` plus a Postgres checkpointer match the Approve/Edit/Skip flow. Alternatives considered: Strands, Pydantic AI, OpenAI Agents SDK, a hand-written loop.
- **CPU-only open models, no paid APIs.** A cost router (rules → small GEC model → local LLM) keeps the expensive tier rare. Models are configuration; an unscoped model is added as an eval experiment.
- **Arize Phoenix via OpenTelemetry** for traces and evals: one container, where a self-hosted Langfuse needs about six. Moving to Langfuse is an exporter change; datasets would not migrate. LangSmith skipped: traces would leave the machine.
- **Prometheus + Grafana**, kept to one dashboard and one alert.
- **Cards hold chunks, the bot drills sentences:** long sentences make poor Anki cards, and the bot can grade full sentences where Anki cannot. Provisional until used.
- **Build the fixed workflow first (unit 3), then the agent (unit 7)**, and compare them on the same eval: the agent has to earn its extra cost.
- **MbxRead is an optional tool** over `host.docker.internal`; the bot works without it.
- **Content imported wide and pruned later**; personal sources stay in the local database.

## 2026-11-22 Unit 0: scaffold
- **Hashed lock from the start:** `requirements*.in` compiled by pip-tools into `requirements*.txt` with `--generate-hashes`; the image and CI install with `--require-hashes`, so every transitive package is pinned and verified. uv would do the same faster; it is not installed here and pip-tools is enough. Compiled on Windows, so the lock includes `tzdata` and `colorama` (Windows-only markers dropped); both are harmless on Linux, and the Linux image build proves nothing is missing.
- **Only what unit 0 uses is installed** (psycopg; pytest for dev). LangGraph, python-telegram-bot and the rest arrive with the units that use them.
- **The app process is a stdlib health server** (`/health`, 200 or 503 by a `SELECT 1`), so compose and CI have something real to check before the bot exists. Unit 1 builds the bot around it.
- **Postgres image reuses MbxRead's pinned pgvector image** (Postgres 18): already vetted and pulled, and the vector extension is there if learner memory ever wants it. Actions reuse MbxRead's SHA pins (vetted 2026-11-18).
- **Ports:** health `127.0.0.1:8005`, db `127.0.0.1:5434`.
- **Verified:** 5 tests; image 133 MB, runs as uid 10001; compose healthy; health goes 503 when db stops and back to 200 when it returns, no traceback.

## 2026-11-22 Unit 1 design: commands and chat UI
- **English UI, Korean content; no persistent reply keyboard** (user): the `/` menu plus inline buttons keep the chat clean.
- **Free text outside a session is assumed to be a capture, confirmed with one tap** (user): fewer accidental captures for the cost of one button.
- **Buttons edit their own message in place** and callback data carries only a short key into Postgres: the chat reads as a record of outcomes, and Telegram's 64-byte callback limit never constrains a payload.
- **A live progress message** covers CPU latency and makes the router's tiers visible.
- **The `/` menu is scoped to the allowed chat**, so strangers see no commands; set from code so it cannot drift from the handlers.
- **Grammar explainer added (user):** `/grammar <form>` and a `[📖 Grammar]` button on practice prompts, served from the NIKL pool's refreshers with no model call. Basic points (level-1 particles to start, grown by `[✓ I know this]`) are never offered. Lands with content import (unit 2) and the practice loop (unit 5).

## 2026-11-22 Unit 1: bot skeleton and UI kit
- **python-telegram-bot 22.8** (June 2026, the newest release past the two-week rule). Alternatives: aiogram (async-first, router-based, popular in Russian-speaking communities), pyTelegramBotAPI (simpler, sync by default), raw Bot API over httpx. PTB has the largest docs and examples, a built-in JobQueue for the pings (unit 5) and typed objects for every Bot API feature used here (copy-text buttons, reactions, expandable quotes).
- **The allowlist is one `TypeHandler` in group -1** that raises `ApplicationHandlerStop` for anyone else, so no handler, present or future, can forget the check. Strangers get silence (no reply reveals that the bot is alive for someone).
- **The `/` menu is generated from the `COMMANDS` list** and set at startup: default scope cleared, the allowed chat scoped. The help text is built from the same list.
- **"Capture this?" quotes the user's message** (`do_quote`), and the callback reads the text back from `reply_to_message`. No callback payload and no state table are needed yet; the Postgres-backed key arrives when a button must carry data that is not on screen (unit 3).
- **Telegram network errors are logged, not sent to the chat:** polling already retries them, and a chat message during an outage would fail anyway. Everything else is reported in the chat.
- **`httpx` logging held at WARNING:** at INFO it logs every request URL, and Bot API URLs contain the token. Verified: the token does not appear in the container logs.
- **Pending updates are processed after a restart** (not dropped): a message sent while the bot was down still gets handled; Telegram keeps updates for 24 hours.
- **Tests mock Telegram entirely** (handlers called with `MagicMock`/`AsyncMock`, run with `asyncio.run`), so CI needs no token and no network; no pytest-asyncio dependency.
- **Verified:** 26 tests; compose healthy, survives a restart; menu empty in the default scope and `help`, `demo` in the allowed chat; every demo button checked on the phone by the user.

## 2026-11-22 Unit 2: content import and /grammar
- **Public pools copied into `data/`** (from MbxWrite `5ae386f`) rather than read from the MbxWrite install: the repo goes public, the image and CI need the files, and tests can check the counts. MbxChat now owns its copy; re-copy to sync.
- **One `item` table** (`kind`, `key`, `level`, `ko`, `en`, `data jsonb`, unique on kind + key) for grammar, sentences, words, wishes and terms. Practice (unit 5) draws from all of them, and their fields barely overlap, so the rest lives in `data`. Vocabulary grades A/B/C stay in `data`; they are not mapped onto levels 1-6.
- **Each kind is replaced as a whole** (upsert, then delete keys the source no longer has), in one transaction. Re-imports keep ids, and deletions at the source carry over. Revisit when practice history references items (unit 5): deleting a practised item may need to archive instead.
- **Public import runs at every bot start; personal import is a host command.** The container cannot see `write.db`, and personal data should move only when the user asks. A source that is not set or not reachable is skipped with a reason and its rows are kept.
- **Known grammar is its own table** (`known_grammar`), so re-imports never reset it. Seeded with 13 level-1 particles (이/가, 과/와, 까지, 은/는, 도, 을/를, 부터, 에, 에서, 의, 하고, 만, 보다), for the user to review; `[✓ I know this]` adds more.
- **`/grammar` matching is deterministic:** hyphens, digits and spaces dropped, parenthesised parts optional, the NIKL `related` column supplies the allomorphs. Exact match first, then either side of a slash, then substring. Two senses of one form (`-는데1`, `-는데2`) give a choice of buttons that edit the message in place.
- **DB calls from handlers are sync psycopg in `asyncio.to_thread`:** psycopg's async driver cannot run on Windows' default event loop, where the tests run, and one user does not need a pool.
- **Verified:** 52 tests; live counts match the sources (grammar 336, sentence 20, word 5543; wishes and terms match their sources, numbers kept out of the repo); a second import changes nothing; personal rows survive a bot restart.
- **MbxWrite is a one-time source (user):** its future is open, so the data files are a fork owned here (never re-synced) and wishes import once; later runs skip them. MbxRead terms still refresh on every run.
- **Known is reversible:** asking `/grammar` for a known point offers `[↩ Not known]`. Basics are seeded on the first import only, so an un-known basic stays un-known across restarts.
- **Nothing reads MbxWrite at run time (user, hardening):** MbxWrite will not exist in production. The wish importer, `MBXWRITE_DB` and their tests are removed after the one-time import; the `wish` kind stays in the schema for the imported rows. The Postgres volume is now the only copy of those wishes, which makes backups (hardening pass after unit 4) matter.

## 2026-11-22 Unit 3: capture as a fixed workflow
- **Ollama is MbxRead's compose service** (user): same `gemma4:e4b`, no second 6.6 GB copy, and our own CPU service would be no faster. It runs on CPU (not the GPU, as first assumed). If MbxRead is retired, MbxChat gets its own service; only `OLLAMA_URL` changes.
- **Thinking off** (`reasoning=False`): gemma4 spent ~900 hidden tokens and 70 s on a two-sentence draft; off, the same call takes ~5 s. A capture is ~30-50 s end to end.
- **krdict through MbxRead's `/api/dict`, not a client of our own:** MbxRead already caches lookups and stops all calls after one failure, and krdict has blocked this IP for bursts. One client per IP keeps that rule in one place; no second key, no XML parsing. MbxChat still spaces lookups 3 s apart. Cost: krdict is unavailable when MbxRead is down, which the workflow tolerates.
- **Library usage was already there** (MbxRead `POST /api/usage`, unit 5 of MbxRead), so no MbxRead change was needed (user chose "add an endpoint" before this was found).
- **krdict only for lemmas outside the NIKL pool** (user); usage for up to two lemmas outside the pool or graded B/C. Grade-A words gave useless usage hits (주, 회사).
- **One thread per capture**, not per chat: several captures can wait on buttons at once.
- **The bot drives the graph; the graph sends nothing.** Telegram messages are sent from the handler after each stream step and interrupt, so no node has a side effect that a resume could repeat. `review` holds one `interrupt()` per chunk and only collects decisions; `save` writes with `ON CONFLICT DO NOTHING`.
- **Sync LangGraph in worker threads** (`asyncio.to_thread(next, stream)`), same reason as unit 2: the async Postgres driver fails on Windows' default loop, where tests run. The checkpointer sits on a `psycopg_pool` pool so a dropped connection is replaced instead of poisoning every later capture.
- **Model output is cleaned in code where the model is unreliable:** shortened source sentences are mapped back to the full reviewed sentence, and critic entries without `→` are dropped (gemma sometimes returns `["casual", "polite"]`). Prompt quality is left to the unit 6 eval.
- **Phoenix 21.0.0, auth off:** it enables auth for any non-loopback bind, which a container always is; the port is published on 127.0.0.1 only, like the health endpoint.
- **Model pin:** Ollama pins by tag only, so the expected digest prefix (`dc35e8d9c606`) is config and checked at startup with a warning.
- **Term import guard** (from a side review during this unit): an answer with under half the stored terms is refused, so a wrong or empty MbxRead cannot wipe the pool.
- **Image 133 → 460 MB** (kiwipiepy model, numpy, gRPC for OTel). Accepted.
- **Verified:** 65 tests (real graph and Postgres checkpointer; model and MbxRead faked). Live, outside Telegram: three captures ran end to end (~28-50 s), the approved chunk was saved, and a traced run showed 19 spans in Phoenix covering every node and model call.
- **Phone check (user):** one real capture ended in an approved chunk; the trace shows all six nodes and three model calls. The wait is acceptable: the chat is asynchronous and chunks come one at a time, so the user does not sit and watch it.

## 2026-11-22 Unit 4: Anki
- **The `chunk` table is the outbox** (`anki_note_id`, `anki_error`), not a separate queue table: every approved chunk belongs in Anki, so "queued" is just "no note id yet".
- **Idempotency by tag, not by AnkiConnect's duplicate check:** that check compares the first field only (the gloss), which can repeat across chunks and misses nothing about the chunk itself. Each note gets `mbxchat-<uid>` and a push runs `findNotes` before `addNote`, so a crash after the add finds the note instead of adding it again. One lock serialises the bot's push and the retry loop.
- **Tag on a uuid, not the chunk id** (from a side review during this unit): ids restart if the database is recreated, and a new chunk would then match an old note's tag and silently never reach Anki.
- **Plain HTTP to AnkiConnect for now:** the MCP server that will front Anki is unit 7; this module becomes its tool then.
- **Retry loop: every 60 s, silent while Anki is closed**, one log line per new error, one chat message when queued cards land. A refused note is parked, not retried every minute.
- **Own deck and note type** (`MbxChat`, `MbxChat Chunk`) rather than the user's existing `Korean` deck and `Korean Sentence` type: nothing the bot does touches cards it did not make. Both are config/constant; moving the cards later is an Anki browser job.
- **Blank by morphemes** (kiwipiepy, already in the image): chunks are often in dictionary form (`일이 산더미처럼 쌓이다`) while the sentence is conjugated (`쌓였어요`), so a string search misses them.
- **MbxRead example on the back deferred:** capture's usage hits are per lemma, not per chunk.
- **Phone check (user):** approved with Anki closed, the bot said it was queued; opening Anki, the retry loop delivered it and the card appeared once.
- **Capture context goes into unit 5 (user):** text after `//` becomes the situation, stored on `capture` and passed to draft, critic and chunks. Today context typed in the message reaches the draft step only, which is enough for a translation; unit 5 drills need the situation for register.

## 2026-11-22 Cycle 1 hardening pass (units 0-4)
Checked, evidence first:
- **Logs:** bot clean (one start since the unit 4 deploy, no warnings); phoenix only trace POSTs; db 1186 lines, 549 of them `checkpoint starting: immediate force wait`, which is the tests' `CREATE DATABASE ... TEMPLATE` (one per test), harmless, and every service's logs rotate at 10 MB × 3. No stray test databases left behind.
- **Long-lived state after errors:** checkpointer on a pool that replaces dead connections (unit 3); every other DB call opens its own connection; the Anki retry loop catches everything, logs a repeated error once, and stays silent while Anki is closed.
- **Unbounded growth:** LangGraph checkpoint tables (~200 KB after a few captures) and Phoenix traces (2.7 MB) have no retention. Tiny at one user; proposed for unit 9, not done.
- **Config drift:** schema changes are `ADD COLUMN IF NOT EXISTS` at startup, so an existing install picks them up (the unit 4 columns reached the live DB that way). The Anki note type is created once and never updated, so a template change in code does not reach it; noted in STATUS, edit it in Anki if ever needed.
- **Pins:** images by digest, actions by SHA, Python deps with hashes, Ollama model by digest check. Nothing floating.
- **Silent overwrite:** the term import refuses a short answer; Anki notes are only added, never updated; nothing else computes names.
- **Found and fixed: no backups.** The Postgres volume was the only copy of the imported MbxWrite wishes and of every capture. Added MbxRead's `backup` service (nightly `pg_dump -Fc`, newest 14, same pinned image) and a README restore section. Verified: first dump written; restored into a scratch database, row counts of item, chunk, checkpoints and known_grammar match the live DB. The dumps sit on the same disk; copying them off the machine is left to the user.

## 2026-11-22 Skills from cycle 1 (user)
- **`finish-unit` (`.claude/skills/`):** the close-a-unit sequence (tests, docs, commit, PR, CI watch, post-merge branch) ran five times in cycle 1 and slipped twice: a follow-up pushed toward an already-merged PR, and "no checks reported" read right after `gh pr create`.
- **`hardening-pass` (user-level, `~/.claude/skills/`):** the cycle 1 pass took real re-derivation (log normalization, restore check) and returns after units 8 and 11 and in other repos. Indexed in this repo's CLAUDE.md and the user's global one.
- **`capture-smoke` not written:** unit 4 did not need it; the user reconsiders if the pattern repeats.

## 2026-11-22 Unit 5: practice loop
- **Capture situation after `//`** (user), stored on `capture` and passed to draft, critic and chunks.
- **Translation and grammar prompts, new items alternating; grammar rotates widely** across the pool (user). Captures feed practice directly: they are the first translation source.
- **Wishes are not drilled** (user): the two imported wishes go through capture at the end of cycle 2, then the `wish` kind leaves the plans.
- **Sessions close after 30 min idle** (user). A late answer to a prompt from the last 12 h is still accepted through a button on "Capture this?".
- **Pings from a 30 s loop in the bot, not PTB's JobQueue:** JobQueue needs APScheduler (a new dependency), and the loop stores the last ping in Postgres, so a restart neither repeats nor drops one. Pings more than 30 min late are skipped. SPEC §4 updated.
- **`PRACTICE_TZ` lives in `.env`**, not the repo; the container runs on UTC. `tzdata` was already a locked dependency.
- **No LangGraph for practice:** grading is one call with no pause inside it.
- **Grader field order is generation order:** with `verdict` first, gemma said "correct" while fixing the sentence; listing issues and the corrected sentence first, plus a code check (a fix forces "minor"), closes that. `natural` was renamed `model_answer` because gemma answered "very natural" instead of a sentence.
- **Grading quality is for the unit 6 eval:** live, gemma leaves `issues` empty and explains in `note`, rewrites good answers toward the reference (so they count as minor), and graded 반말 to a boss as minor. Not tuned by feel.
- **Reusable loop helper** `forever()` runs both background loops (Anki retry, pings): every call guarded, a repeated error logged once.
- **Verified:** 88 tests (model faked; real Postgres). Live: grader on three real answers, 9-19 s each; pings run on the configured zone.
- **Phone check (user):** the 21:00 KST ping opened a session on time; an answer was graded live (minor, next due in 3 days). The miss path (wrong → due tomorrow) is covered by tests, not yet seen live.

## 2026-11-22 Unit 6a: eval groundwork
- **Unit 5 miss path seen live** (correcting the note above): in the user's full test a deliberate miss put the capture at step 0, due the next day; correct answers moved to step 1, minor held step 0, a skip created no drill row.
- **Unit 6 split into 6a and 6b (user):** the labeled set is proofread by the user in an `.md` file at their own pace, which gates the eval; groundwork that does not depend on it ships first.
- **Model survey, 2026-11-22, from the Hugging Face API** (not memory). Host: Ryzen 5 5600X, 6 cores, Docker 31 GB RAM, CPU only.
- **GEC finding:** open Korean GEC models target native writing. dadeum-gec-base's own card scores it F0.5 .80-.90 on native text and .089 on Kor-Lang8 (learner writing corrected by people); the best on learners, gec_kr, reaches .266. (Their table, with Claude-written gold.) So the GEC tier cannot say "this answer is correct"; it becomes a hint source, and a reference match is the only free verdict. SPEC §6 updated.
- **Included, and why:**
  - `gemma4:e4b` (Google, 8B E4B, Apache-2.0): the production model; the baseline every other model is measured against.
  - A.X 4.0 Light (SKT, 7.3B, Apache-2.0, 2025-07): trained Korean-first; the only A.X that fits a CPU (A.X-K1/K2 are 100B+ class).
  - Mi:dm 2.0 Mini (KT, 2.3B, MIT, 2025-07): Korean-first at a third of gemma's size; tests whether small and Korean-native matches large and general at a fraction of the latency.
  - Nemotron-3.5-Bolt-E4B (NVIDIA, 8B E4B, OpenMDW-1.1, 2026-10): the newest model in gemma's size class, Korean listed, trending; a like-for-like challenger.
  - Olala-v1.0-mini-7A1B (OVH, 7B MoE with 1B active, Apache-2.0, 2026-10): the speed candidate; only ~1B parameters run per token, so CPU latency could drop several times.
  - Qwen3.5-4B (Alibaba, 4.7B, Apache-2.0, 2026-02): the most-used open family; a widely known reference point in the middle of the size range.
  - `dadeum-gec-base` (124M KoBART, CC BY-SA 4.0, 2026-11): tier 1 hint source; minimal edits, guards against rewrites, ~120 ms per sentence.
- **Left out, and why:**
  - `Soyoung97/gec_kr` (2022): rewrites freely, so its output cannot serve as minimal-fix hints, and .266 on learner text is too low to decide verdicts.
  - `j5ng/et5-typos-corrector`, KoGrammar (theSOL1): typo-only, and below dadeum on every column of its comparison.
  - kanana-2-3b-instruct (Kakao): Korean-native, but under Kakao's own licence; Mi:dm Mini fills the small Korean-native slot under MIT.
  - LFM3-1.7B (LiquidAI): licence capped by revenue; Korean is one of many languages; the small slot is taken by Mi:dm Mini.
  - Qwen3.5-9B, Mi:dm 2.0 Base (11.5B): same families as shortlisted models, slower on CPU; added only if their smaller sibling comes close to the top.
  - EXAONE 4.0 1.2B / 4.5 33B (LG): non-commercial licence; the repo goes public and keeps to open licences.
  - HyperCLOVA X SEED 0.5B/1.5B/14B (Naver): no small release since 2025; 14B too slow on CPU.
  - A.X-K2, K-EXAONE 2.0, Solar Open, LFM2.5-24B-A2B: 24B-750B total parameters; beyond 31 GB RAM at usable quantization, or too slow.
- **Labeled set as an `.md` with a `check:` line per item** (user): proofread at the user's pace; 6b parses it and uses only checked items. 66 items: 18 correct (false-alarm check), 48 with known errors across spacing/spelling, particles, voice/tense/form, register/honorifics, connectives and missing target grammar, word choice, and mixed. Verdict rubric at the top of the file.
- **Moving hosts** (user question): quality scores carry across machines, latency and RAM fit do not; a new host reruns the harness for latency only. SPEC §6.
- **Corrected line as a word diff** (`ui.word_diff`, difflib over words): changed words as <s>old</s> <b>new</b>; the model answer is dropped when it equals the corrected sentence (spaces and punctuation ignored).

## 2026-11-23 Unit 6b: cost router and model eval
- **Picked: `gemma4:e4b` for both grading and capture** (user). Config defaults stay as they are (`CAPTURE_MODEL=gemma4:e4b`, ID `dc35e8d9c606`; `GRADER_MODEL` falls back to it). It is the only model with no hard failures in either role, the best grader on verdicts and corrections, and the fastest of the strong ones.
- **Method.** Grader: the proofread set (`grader_set-499d7ab3`, 66 items: 18 correct, 48 with labeled errors), one Phoenix experiment per model, per-item outputs in `evals/results/grader-*.json`, one summary line per run in `evals/results/grader_summary.jsonl`. Scored as: *verdict* (exact match with the label), *false alarm* (a correct answer flagged), *missed* (an answer with errors called correct), *correction right* (every labeled fix appears in the corrected sentence; a correct answer must come back unchanged). Capture: 10 English prompts written for the purpose, each through draft → lookup → critic → chunks on every model, judged by the user (`evals/results/capture_side_by_side.md`).
- **Grader results** (GPU run, of 66; CPU runs earlier the same day gave the same picture):

  | Model | Verdict | False alarms (of 18) | Missed (of 48) | Correction right | Median s |
  |---|---|---|---|---|---|
  | gemma4:e4b | 43 | 2 | 9 | 52 | 1.4 |
  | Nemotron-3.5-Bolt-E4B | 43 | 0 | 13 | 48 | 7.0 |
  | Qwen3.5-4B | 38 | 8 | 4 | 32 | 2.1 |
  | Mi:dm 2.0 Mini | 37 | 1 | 19 | 38 | 0.8 |
  | A.X 4.0 Light | 35 | 9 | 6 | 36 | 1.6 |
  | dadeum-gec-base | 24 | 0 | 42 | 24 | 0.05 |
  | gemma + dadeum hints | 40 | 2 | 8 | 53 | 1.6 |

- **Capture results:** gemma 10/10 prompts, A.X 10/10, Qwen 10/10, Nemotron 7/10, Mi:dm 7/10 (the failures are "invalid Chunks twice": malformed JSON after the one retry). Median ~9 s per capture for gemma, ~20 s for Nemotron.
- **gemma4:e4b (kept).** Grader misses are mostly honorifics and connective rules: passed 할머니가 자고 있어요 (needs 께서 주무시고 계세요), 선생님이 그렇게 말했어요 (말씀하셨어요), 비가 와서 우산을 가져가세요 (-아서 cannot lead into a command), 날씨가 춥는데 (추운데), 재료/자료. False alarms: added 뭐 to a correct 필요한 거 있어?, and changed a correct 자는 바람에 to 잔 바람에. Capture: natural drafts in the right register, 1-2 chunks per prompt with real English glosses. Slips: 언니 (older sister) for an aunt in a casual draft, and an awkward 아프기만 했을 때.
- **Nemotron-3.5-Bolt-E4B (discarded).** Ties gemma on verdicts with zero false alarms, but misses voice errors (문이 저절로 열었어, 회의가 연기했는데, 모기가 물렸어) and the ㅂ-irregular 돕았어요, and makes fewer corrections. 5x slower than gemma on GPU; on CPU it wrote ~600 tokens per answer (60 s median). Capture failed on 3 of 10 prompts, gives a single chunk per prompt, leaves slash alternatives in drafts (언니/이모) and typed 아프 때.
- **Qwen3.5-4B (discarded).** Fewest misses (4), but 8 false alarms, some changing the meaning: corrected a correct 수영할 수 없어요 to 수영할 수 있어요, and once returned praise ("문장 구조가 완벽하고 자연스럽습니다") instead of a sentence; one item failed twice. Capture Korean has real errors: 매야요, 상위에서 for upstairs, 잠이 잘 못 쉬었네요, 아줌 / 어머니님 as forms of address, 병들 때; "Could you check the report" became 확인해 드릴까요 ("shall I check it"). Needs `think: false`.
- **Mi:dm 2.0 Mini (discarded).** Fastest (0.8 s) with 1 false alarm, but misses 19 of 48: register (밥 먹었어? to a boss, 이름이 뭐야? to a customer), word choice (감기를 잡았어요, 모자 입어, 몸무게를 잃었어), voice (문이 저절로 열었어). Capture failed on 3 of 10; its chunks are unusable: the literal words "collocations" and "grammar patterns" as chunks, the same sentence three times, an English sentence as a chunk.
- **A.X 4.0 Light (discarded).** 9 false alarms: rewrites correct answers into 합니다 style (운전할 수 있어요 → 있습니다) or changes them (오랜만이야 → 오랜만에, 맛있더라고요 → 맛있어요). Capture answered the first prompt in English, called an aunt 할머니 (grandmother), spoke to a mother-in-law as 엄마 with 너; its chunks are whole sentences with the Korean repeated as the gloss.
- **Olala-v1.0-mini-7A1B (dropped before the eval).** Ollama 0.40.15 fails with "unknown model architecture: 'olala'"; the model card says upstream llama.cpp and Ollama do not support it (vendor fork only).
- **dadeum-gec-base and the hint tier (dropped).** Never flags a correct answer, but edits only 6 of the 48 answers with errors; 18 of its 24 right corrections are correct answers left alone. As hints to gemma (one "a spelling checker suggests" line when dadeum changes the answer): 40/2/8/53 against gemma alone 43/2/9/52, within run-to-run noise (gemma's CPU and GPU runs already differ by one miss). The bot does not run dadeum; `grade()` keeps an optional `hint` used only by the eval harness (`<model>+dadeum`). SPEC §6 updated.
- **Router / tier mix.** Tier 0 (reference match → correct, no model call) is kept: free and tested. It hit 0 of 66 set items and 0 of 5 live answers with a reference, so in practice almost every answer takes the LLM path. With the GPU that path costs ~1.4 s, so the router is not a meaningful cost lever today.
- **Scoring caveat, all models alike.** `grade()` compares sentences with spaces stripped, so a spacing-only fix keeps the verdict `correct`. The three spacing items (집에가서 쉴거야, 늦을것, 가고싶어요) count as missed for every model that fixed them (gemma fixed all three). It does not change the pick; whether spacing slips should be graded minor is an open question in STATUS.
- **GPU.** Ollama failed with `cuInit failed: 500` ("named symbol not found"): the `libcuda.so.1` packaged in Docker Desktop was older than the Windows driver. Updating Docker Desktop (4.99.0) fixed it with no compose change. gemma warm: 159-192 tokens/s on GPU against ~9 on CPU.
- **Models evaluated, Ollama digests (prefix):** `gemma4:e4b` `dc35e8d9c606`; `hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M` `9f0107f24601`; `hf.co/mykor/Midm-2.0-Mini-Instruct-gguf:Q4_K_M` `68bc4560da12`; `hf.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF:UD-Q4_K_XL` `7988467f401f`; `hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M` `d31742299266`; `hf.co/OVHaiLLM/Olala-v1.0-mini-7A1B-GGUF:q5_k_m` `27bdade0292b`; dadeum-gec-base at revision `d2af339da05d89750c38db6331b3ddbd3b3d5219`. All but gemma removed from Ollama after the pick.
- **Harness notes.** Run with `PYTHONUTF8=1` when output goes to a file: Phoenix prints emoji and a cp949 console encoding crashes the run. In the capture run, one Mi:dm prompt took 296 s because a live bot capture used the same Ollama at the same time; its output is unaffected.

## 2026-11-23 Unit 7 plan
- **Scope (user):** capture becomes a tool-calling agent; free text inside a session gets routed (answer / capture / question). The agent choosing the next drill moves to unit 8 or later: the ladder already schedules well, and an LLM pick only adds value once practice data exists to reason over. SPEC §7e, §8.
- **Single-word capture (user):** "the word for optimization, a coworker said it" → the Korean word, a dictionary check, 2-4 examples, one Anki card. Cards only, low volume, not used by practice.
- **Standalone rule (user):** the repo must run for anyone. Anki writes never go through MbxRead: word cards use MbxChat's own outbox, note type `MbxChat Word`, deck `ANKI_WORD_DECK`. Writing into MbxRead's deck was checked: MbxRead's sync only touches notes it created (by stored id) and never deletes, so pointing `ANKI_WORD_DECK` at it is safe; a separate note type keeps Anki's duplicate check apart.
- **MbxRead becomes opt-in:** `MBXREAD_URL` empty by default (features off and silent); set, its library examples and saved terms are used. MbxChat gets its own krdict client so dictionary checks work without MbxRead. Sharing MbxRead's Ollama stays; the README says MbxRead material is used when present and ignored when not (unit 11).
- **Tool-calling check** (`evals/tool_calling.py`, fake read-only tools, 10 prompts × 2 runs): `gemma4:e4b` 20/20 finished, 20/20 right path, 0 malformed calls, 0.65 s median; `gemma4:12b` (Ollama `6114515d63c1`) the same mechanics, better chunks and always fetched library examples, but 16.9 s median (8 GB model on an 8 GB GPU, partly on CPU). e4b kept, no model router. Raon-1 nano (KRAFTON, Korean + tool calling, Apache-2.0, 2 GB) left out: its card requires KRAFTON's llama.cpp fork, so Ollama cannot load it (like Olala).
- **Grounding enforced in code:** with a free choice, both models skipped the dictionary on 19 of 20 sentence captures and e4b wrote its own examples for 9 of 10 words (and looked up English words 3 times). So the dictionary check and library examples run as fixed steps; the agent decides the capture kind, the Korean, and what to do with the results.

## 2026-11-23 Unit 7 build (steps 1-7; closing lines with the PR)
- **MbxRead opt-in:** `MBXREAD_URL` defaults to empty and compose no longer sets it; features are off and silent without it. The host importer never read `.env`, so it now needs the variable in its shell.
- **Own krdict client, sparse across processes:** cache in Postgres (`krdict_cache`), 3 s gap and 30 min pause stored in `setting` and serialized by a Postgres advisory lock, because the bot and the `mcp` server are separate processes and an in-process lock would let them double the rate. One live request checked the key (최적화 → 0 entries: the learners' dictionary misses many work words, so a word with no entry is kept and its root looked up once).
- **MCP server** on the bot's image as its own compose service, streamable HTTP, no host port; a tool is offered only when its backend is configured. `mcp==1.30.0` (the last 1.x: `langchain-mcp-adapters==0.3.2` needs `mcp<2`). `pip-compile` on Windows pinned `pywin32` unconditionally and broke the Linux image build; the lockfile line carries the `sys_platform == "win32"` marker by hand.
- **Rebuild everything, not `bot` alone:** `bot` and `mcp` share the image; `docker compose up -d --build` with no service name recreates both (flagged by a side review; `finish-unit` updated).
- **Agent:** its own small tool loop over LangChain's MCP adapters (max 6 steps), with `submit_word` / `submit_sentence` as the only way to finish; a malformed submit is returned to the model as a tool error. gemma4:e4b sometimes writes a tool call as text (`submit_sentence(casual="…")`): accepted when it parses with literal arguments only (`ast`), which fixed 4 of 10 failed sentence runs in the eval.
- **Word path:** examples must contain the word's stem, from every source: krdict's entry page mixes in examples of related entries, and the model once picked 데드라인 while writing examples with 마감일. Library hits must also be full sentences (transcript fragments dropped; user). `capture.kind` keeps word captures out of practice prompts.
- **Session routing:** a free tier first (Korean with a space = answer, no call; a single Korean word = capture offer), then one structured call for the rest. Every non-answer is offered all options (`[➕ Capture] [💬 Answer it] [✍️ Grade it as my answer]`); the guess only orders them, because the live check misread "how do I say I am stuck in traffic" as a question. Convention (user): in a session, Korean phrases are answers; captures and questions are written in English.
- **Eval, workflow vs agent** (`evals/capture_ab.py`, 10 sentence + 5 word inputs, nodes called directly, no rows written): sentences 3 model calls each, workflow 3.4 s vs agent 2.75 s median, agent 0 tool calls on all 10 and flatter drafts (봐주세요 vs 검토해 주실 수 있을까요? to a boss; one register pair left identical and unfinished); words agent 0.8 s with dictionary line and examples, workflow echoes the word as two "sentences". 0-1 krdict requests per run (cached).
- **Hybrid, decided with the user from the eval:** in agent mode a sentence goes to the workflow's `draft` node (the agent's draft is dropped); words keep the agent path. The agent's job is the decision and the word path, which is where it measured better.
- **Skill `eval-in-container`** (user, end of session): an eval needing the `mcp` service ran 4 times this unit and the mount path failed once; the procedure now lives in `.claude/skills/eval-in-container/`, indexed in CLAUDE.md. A lockfile-recompile skill was proposed and declined (unlikely to recur).
- **Hybrid built (step 7b):** `CAPTURE_MODE` default is now `agent`. Eval rerun: agent-mode sentence drafts match the workflow's (same draft node; small differences are sampling at temperature 0.2), at one extra model call (4 vs 3, ~+1 s) for the decision. Words unchanged (0.8-1.0 s, 2 calls).
