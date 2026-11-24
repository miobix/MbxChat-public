---
name: record-demo
description: Rerecord MbxChat's demo (demo/conversations.json) from the real bot handlers, then gate it - automatic checks, a human read of every kept run, drop the bad ones with a reason, preview, test. Use after any change to what the bot sends (message text, buttons, grading, capture output), when the user says "rerecord the demo", or when tests/test_demo.py fails after a UI change.
---

# record-demo

The loop from unit 10, run four times there. The contract is SPEC §7h; this is the order of work.

## 1. Record

The recorder runs the image, not the working tree, and calls the real model (Ollama on the host
must be up) and krdict (paced, cached). It uses its own scratch database `mbxchat_demo`, its own
MCP server and an unreachable Anki, so the live stack is untouched.

```bash
docker compose up -d --build        # all services: mcp shares the image
docker compose run --rm --no-deps -v "$(pwd -W)/demo:/app/demo" bot python -m demo.record [Prefix ...]
```

- No prefix: every group is rerecorded and `demo/conversations.json` is replaced.
- A prefix (`Practice`, `Word`) rerecords only matching groups; the others and their dropped runs
  are kept from the file.
- PowerShell: `-v "${PWD}/demo:/app/demo"`. Long runs: background, output to the scratchpad.

Each run prints `group | label | N events | ok` or its failed checks. Failed runs go straight to
`dropped` with their flags.

## 2. Read every kept run (the human gate)

The automatic checks miss wrong Korean, contradictions (a note praising an answer graded down),
and register slips. Dump the kept runs to read them:

```bash
PYTHONUTF8=1 python -c "
import json,re;d=json.load(open('demo/conversations.json',encoding='utf-8'))
for g in d['groups']:
  for it in g['items']:
    print('==',g['title'],'|',it['label'])
    for e in it['events']:
      t=e.get('text') or re.sub('<[^>]+>','',e.get('html') or '') or e.get('label','')
      if t: print(' ',e['op'],':',t)
" > <scratchpad>/demo_read.txt
```

Read the whole file. For each bad run, drop it with a reason a reader would understand:

```bash
DATABASE_URL=postgresql://unused@127.0.0.1:1/x .venv/Scripts/python -m demo.record drop "<label>" "<reason>"
```

(The fake `DATABASE_URL` is needed only because the module reads it at import.)

## 3. Check and preview

- If drops leave a group nearly empty, rerecord that group by prefix and read again (the
  unit 10 recording kept 3 to 6 runs per group).
- `.venv/Scripts/python -m pytest tests/test_demo.py -q` (every tap hits a button that existed).
- Preview: `python -m http.server` in `demo/`, then `http://127.0.0.1:8000/#0`…`#3`.

## 4. Record the outcome

In the unit's DECISIONS entry: kept vs recorded, and how many failed the automatic checks vs the
read. Anything the read found in the bot itself (not just this recording) is a finding: fix it or
list it, don't just drop the run. Never hand-edit `conversations.json`; the page claims every run
went through the bot.
