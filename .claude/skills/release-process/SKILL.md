# Skill: release-process

End-to-end release procedure for SC Signature Reader.
Use this skill whenever the user asks to "release", "tag", or "bump version".

## Pre-release gate (always run first)

```powershell
cd sc_signature_reader
.venv\Scripts\python scripts/check_release.py
```

**All three gates must pass before proceeding:**
1. Tests — 474 tests, 0 failures (test_ocr_fixtures.py excluded)
2. Coverage — every tracked module ≥ 90 % line coverage
3. Version consistency — `main.py VERSION` == `SCSigReader.iss AppVersion`

If coverage fails, stop and tell the user which modules are below threshold.
Do not release with failing tests or a broken version match.

## Files to update for every release

| File | Field | Example |
|------|-------|---------|
| `main.py` | `VERSION = "X.Y.Z"` | `VERSION = "1.4.4"` |
| `SCSigReader.iss` | `#define AppVersion "X.Y.Z"` | `"1.4.4"` |
| `.github/workflows/release.yml` | `files: installer/SCSigReader_Setup_X.Y.Z.exe` | update filename |
| `CHANGELOG.md` | new `## [X.Y.Z] – YYYY-MM-DD` section at the top | see format below |

Update all four files atomically in a single commit.

## CHANGELOG format

```markdown
## [X.Y.Z] – YYYY-MM-DD

### Fixed
- **Short title** — one-line description of root cause and fix.

### Added
- **Feature name** — what it does, who benefits.
```

Rules:
- Lead with the user-visible impact, not the implementation detail
- "Fixed" before "Added" before "Changed"
- Max 80 chars per line in bullet bodies

## Commit and tag sequence

```powershell
git add main.py SCSigReader.iss .github/workflows/release.yml CHANGELOG.md
git commit -m "chore: bump version to X.Y.Z

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git tag vX.Y.Z
git push
git push --tags
```

**If `git push` is rejected** (remote has diverged):
1. `git pull --rebase` — if conflicts arise in the files listed above, resolve them:
   - `app_state.py`: keep the implementation in `_save_config()`, `save_config()` as public wrapper — never let them call each other (recursion)
   - `setup_wizard.py RESOLUTIONS`: keep ALL presets from both sides
   - `setup_wizard.py hint text`: keep the dynamic `"\n".join(hint_lines)` path
2. Run `scripts/check_release.py` again after resolving
3. Continue push

## CI monitoring

After the tag push, monitor GitHub Actions:
```powershell
gh run list --limit 5
gh run watch   # stream the latest run
```

The release workflow (`release.yml`) runs on every `v*` tag:
- Runs tests → installs Tesseract → generates assets → PyInstaller → Inno Setup → publishes GitHub Release
- Expected duration: 8–12 minutes

If the workflow fails, check the failing step:
- **Tests fail on CI but pass locally**: check if a new test file was added but not listed in the `ci.yml` test command
- **PyInstaller fails**: a new module was added but not listed in `--add-data`
- **Inno Setup fails**: `SCSigReader_Setup_X.Y.Z.exe` filename in `release.yml` doesn't match `AppVersion` in `SCSigReader.iss`
- **Release upload fails**: the `files:` path in `release.yml` doesn't match the built installer filename

## Versioning rules

`MAJOR.MINOR.PATCH`:
- PATCH: bugfixes only (no new user-visible features)
- MINOR: new features, backwards-compatible
- MAJOR: breaking changes or major architecture shift (e.g. tkinter → PySide6)

Current series: 1.4.x — feature-complete tkinter baseline.
Next major milestone: 2.0 (PySide6 migration).

## Hotfix releases

When a bug is found immediately after a release (like the config.json permissions issue):
1. Fix the bug on `main`
2. Run pre-release gate: `python scripts/check_release.py`
3. Bump PATCH version only
4. CHANGELOG entry under `### Fixed` only
5. Tag and push as normal

Do NOT squash or amend the previous tag — create a new tag.

## Coverage monitoring

The coverage gate is enforced by `scripts/check_release.py`.
See `reference/coverage-gates.md` for per-module thresholds and history.

If a module drops below 90 %:
1. Identify which lines are uncovered: `pytest --cov=<module> --cov-report=term-missing`
2. Add tests for the uncovered paths
3. Re-run the gate before releasing

The CI job also reports coverage in the Actions summary dashboard.
