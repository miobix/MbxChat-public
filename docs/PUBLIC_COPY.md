# Public copy (reference: how this repository was made)

This repository is a public copy of a private one, made with
[git-filter-repo](https://github.com/newren/git-filter-repo). Development history is kept
whole; only personal data was rewritten. This page lets you check that claim.

## What was rewritten

- **Test fixtures:** a few test sentences came from the author's real practice use. They were
  replaced with synthetic sentences that keep the same mistake, so each test still tests the
  same thing (a misspelt word stays misspelt, a missing space stays missing).
- **Author name:** the merge commits made on GitHub carried a different display name; every
  commit is now authored as `miobix` with the GitHub noreply address.
- **A few doc lines:** an early tagline, two short mentions of steps outside this project, and
  one local file path.
- **Merge messages:** "Merge pull request #N from …" became "Merge branch … (private PR N)", so
  they don't link to unrelated pull requests here. The pull requests themselves (descriptions,
  CI runs) stay on the private repository.

Nothing else changed: no commits were removed, squashed or reordered.

## Evidence

Measured by comparing every private commit with its public counterpart:

- **82 commits, mapped one to one.** The file list is identical in every commit:
  yes. Author and commit dates changed: 0.
- **Files whose content ever differs** (number of commits in which they differ):

| File | Commits |
|---|---|
| `docs/SPEC.md` | 79 |
| `tests/test_anki.py` | 57 |
| `tests/test_ui.py` | 45 |
| `tests/test_practice.py` | 9 |
| `CLAUDE.md` | 4 |
| `README.md` | 4 |
| `docs/STATUS.md` | 3 |

`docs/DECISIONS.md` (the reasoning), all code under `mbxchat/`, `evals/`, `data/` and `demo/`
are byte-identical in every commit. `docs/SPEC.md` differs in almost every commit only because
one removed sentence was there from the start.

## Commit map

Private commit → public commit (first 12 characters), oldest first. Anyone given access to the
private repository can compare any pair.

```
01fd59fcc2f0 ac9261bd7e3c
0204464c16ae a41a778a7697
0662d1b7a629 f3044d761733
08161fb6ec37 25db6a5c8f7b
0b42e0e567bf c08f2a38b9e6
17e4b46244df 6c4c8566374b
1a75aae6b5f6 3051d4f2eb24
202807889cc8 88e81cba6ea7
21d1dd8d2d8e 4a640bc75bb3
255c9ece8f9a cfef6ceed3f5
2a5313abb8c5 5d7ee56ee8ef
2b62f791fdcb 5a981e222c31
2d9e449f7ff5 e3fa5a494810
2f01bbc10b9f e63e20f1cd5e
330001d9aa75 4444d06d232b
37fe69c21a90 b5f4e05d7cfe
380f146668e2 475db326302c
396305adafff b29b40355bb8
3a12c317bb49 451ccf456602
46a15ff23e1c 33a40fa2d389
47703c3235e3 d4ef46ef5ed9
4dc7296328f5 ae4dd4a7d19b
503ebf71c556 f01764a93583
51982ddb973f 7fa305896af1
554d20e7a993 cfcb9e4893b6
5a22a88b52e5 117849981f9a
5da8972c8922 d93fda663e1e
5e3ad8bb0a1c aed8460f612f
63fad2aeff69 f19bf7bc641b
669f4148ffcb c5bead7227f9
66c74459d28c f8176cdf4e3a
6967f304504e 302b55a8472c
6a9f5dee2ee6 665dabefd781
6b49c862bcb6 36381bc5eb98
6ba9cc58b6ce 511d5375c696
7279b5fceb58 ce2cb1cc20d0
737700e4980a 157909efe012
740d0e042819 e574248bc5b5
74d7449ebdca d18b85e10af5
7b6b9ab0aa41 750ac20a188d
7d1d5da80fd5 7f88a723b320
801ca1bdd30f 29533da0a16f
81e989bdd982 f7a7350c5b29
831709f8562e d50c0665779a
8407616c6a6e ea900e0d9594
8be12228e567 15f5220f3d57
8da72e422c5c f5d900aa6ade
8e6c161fd5a7 b4c347b286c6
8fc8304dbb69 bbc9275e2d10
92585cff9a66 1b3fd82bff03
927505b4522b be8dc850740e
9e0bb3676334 ca12e095996c
9e4e9b85c31f a6c48b656309
a2a42bde1bda bf914046542d
a4b92178515c 99c3357bc4d3
a5093c8da5de 252ef4615114
ae41462578ac eb032e72da78
aee8ca500f58 93e73893167f
b1cfc1ec4ce0 afe93928c4a4
b2deb935ec73 ca072a413e6f
b60228701247 a165e116a126
b7b6db80396d 3217af95f8a1
b87e301430ad af2dff341a09
b911aea0e74d 82cb6a19079f
bb67eb7e1295 407c10c88304
bfe17337b58a e5a9eb1af01e
c08d3bf7c7bd 9147661448e5
c8d7cb303d6c ca4c5e1f5612
ce2ce1e3bdf6 4d79a2781299
ceb67df1f30c d41e2ba26347
d42c255a72f3 5dbb48646110
d9fd5eda4e83 e4b75e5d544b
dc2e7e2e5289 d038983f0e56
e0373ed9ebf3 706a0b7a601a
e23be172cb3e 2ce6b9e72aff
e25589d18cc1 5a208f5a6fbc
e314bbab2915 8c21f4183d1b
e4c46633eac6 c9147a70e0b9
e53f94100b07 1e3e12167819
e652c9e14a7a c7495a62eb03
f4982afa7fc6 e44e0315e342
f65f38f244e7 b926618c1ac5
```
