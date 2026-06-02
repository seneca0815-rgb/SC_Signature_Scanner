# Contributing to SC Signature Reader

## Dev environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp config.example.json config.json
```

Tesseract must be installed separately — see `README.md`.

## Running tests

```bash
python -m pytest tests/ -v          # all tests
python -m pytest tests/test_core.py -v   # single module
```

CI runs the full suite on every push and PR (Windows, Python 3.11).
All tests must pass before a PR is merged.

## What to contribute

### Lookup entries (`lookup.json`)

The most common and most valuable contribution. If you find a signature value
missing from the database:

1. Note the exact number shown in your HUD.
2. Verify the mineral name and multiplier from in-game market / UEX data.
3. Add an entry to `lookup.json`:
   ```json
   "12345": "MineralName (3x)  ·  Rarity"
   ```
4. If two minerals share the same signature, join with ` / `:
   ```json
   "19200": "Aslarite (5x)  ·  Uncommon  /  Savrilium (6x)  ·  Legendary"
   ```
5. Run `python -m pytest tests/test_integration.py -v` to verify JSON integrity.

Rarity values: `Common`, `Uncommon`, `Rare`, `Epic`, `Legendary`.

### Detection fixtures

New ships or unusual backgrounds (planet surface, heavy nebula) need fixtures.

1. Take a screenshot of the HUD showing the signature pill clearly.
2. Save it under `test_fixtures/<Manufacturer>_<Ship>/detail.png`.
3. Run `python scripts/test_icon_detection.py` — it saves `debug_pill_*.png`
   showing which pills were detected and what OCR returned.
4. If detection fails, note the `median_V` from DEBUG log and update
   `.claude/skills/pill-detection/reference/fixture-examples.md` with the
   measured pill geometry.

### Bug fixes and features

- Open an issue first for anything non-trivial.
- Keep PRs focused: one concern per PR.
- Match the existing code style — no type annotations beyond what's already there,
  no docstrings on obvious functions.

## Commit conventions

```
type(scope): short message
```

Examples:
```
fix(detection): lower pill_aspect_max to 6 to remove high-aspect FPs
feat(lookup): add 12 new Argo MOLE signature values
docs(skills): add pill-detection skill
test(core): add fixture for Krueger Prospector
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`.

## Claude Code & `.claude/` directory

This repo includes `.claude/` — configuration and skills for the
[Claude Code](https://claude.ai/code) AI development assistant.

**Commit `.claude/` with the rest of the repo.** It is not a personal config —
it is project-level context that makes AI-assisted work consistent across
contributors and machines.

### Skills

Project-local skills live under `.claude/skills/`. Each skill is a compact
reference document that tells Claude Code what it needs to know to work
correctly in that domain without re-reading the full codebase.

```
.claude/skills/
├── pill-detection/
│   ├── SKILL.md              ← primary reference (always read)
│   └── reference/
│       ├── threshold-calibration.md
│       └── fixture-examples.md
└── vargo-brand-style/
    └── SKILL.md
```

**When to update a skill:**

| Change | Skill to update |
|--------|----------------|
| New pill detection parameter or threshold | `pill-detection/SKILL.md` |
| New untested manufacturer fixture | `pill-detection/reference/fixture-examples.md` |
| New background environment calibration | `pill-detection/reference/threshold-calibration.md` |
| Brand colour, font, or logo change | `vargo-brand-style/SKILL.md` |
| New theme added to `themes.py` | `vargo-brand-style/SKILL.md` |

Skills use a separate commit:
```
docs(skills): update pill-detection — add Argo MOLE fixture data
```

**Adding a new skill:**

1. Create `.claude/skills/<name>/SKILL.md`.
2. Keep the primary file under ~200 lines — move deep reference material
   into a `reference/` subfolder.
3. Commit with `docs(skills): add <name> skill`.
