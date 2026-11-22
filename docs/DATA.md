# DATA (contract: provenance and licence of every content source)

*Every source that reaches the `item` table has an entry here: what it is, its licence, and how
to rebuild it. Public pools are committed under `data/` and loaded at bot startup
(`mbxchat/importer.py`). Personal pools are never committed.*

The public files were copied on 2026-11-22 from MbxWrite `data/` at commit `5ae386f`
(2026-10-19), once. MbxChat owns them from then on: they are edited here and never re-synced
from MbxWrite. `tests/test_importer.py` checks counts and refresher completeness.

## Grammar pool: `data/grammar.tsv` → `item.kind = 'grammar'`

**Source:** 국립국어원(NIKL), *2017년 국제 통용 한국어 표준 교육과정 적용 연구(4단계)*, attachment
"어휘, 문법 등급 목록_20180227_20201117 수정.xlsx", sheet 문법. 연구책임자 김중섭 외. Report page:
https://www.korean.go.kr/front/reportData/reportDataView.do?mn_id=45&report_seq=932

**Licence:** 공공누리(KOGL) **제1유형: 출처표시** (verified on the report page 2026-10-12 for
MbxWrite). Free use, including modification, with attribution. This section is the attribution;
keep it.

**Content:** 336 points graded 1-6 (45 / 45 / 67 / 67 / 56 / 56). Columns are a faithful copy of
the sheet plus MbxWrite's `id` (`g001`…), which is the item key.

## Refreshers: `data/refreshers/L1.md` … `L6.md` → `item.data` of each grammar point

Original writing (drafted by Claude for MbxWrite, 2026-10-12), not copied from NIKL material. One
section per grammar point, in the file for its level:

```
## g057 -는데 (background, contrast)
register: both | spoken | written | formal | dated
One or two lines of explanation.
- example
- example
vs 다른 형태: optional contrast line
note: optional note
```

Served by `/grammar` with no model call (SPEC §7b).

## Translation pool: `data/translations/L1.tsv` … `L6.tsv` → `item.kind = 'sentence'`

Original writing: graded sentence pairs written for MbxWrite. 20 rows (levels 2 and 3 so far).
Columns: `id, grammar_id, register, ko, en, glosses, added`; the file name gives the level.

## Word pool: `data/vocab_levels.tsv` → `item.kind = 'word'`

NIKL 한국어 학습용 어휘 목록: 5,543 lemmas with grade A/B/C and frequency rank. Identical to MbxRead
`server/data/vocab_levels.tsv`. Published on korean.go.kr with a public-use statement
("목록을 원하는 사람은 누구나 이용할 수 있도록 … 공개"); the download method and the
homograph merge are recorded in MbxRead `docs/DECISIONS.md` (2026-07-22, Epic 13).

## Personal pools (local database only, never committed)

Never committed. MbxRead terms reload with `python -m mbxchat.importer` on the host:

| Kind | Source | Rows taken |
|---|---|---|
| `wish` | MbxWrite `write.db`, table `wish`, non-archived rows, imported once on 2026-11-22. The importer code was then removed: the local database is now the only copy. | - |
| `term` | MbxRead `GET /api/terms` (`MBXREAD_URL`) | status `learning` or `known` |

If MbxRead is unreachable the import is skipped and existing terms are kept. Tests use synthetic
rows only.
