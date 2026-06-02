# Changelog

## [1.4.3] – 2026-06-02

### Fixed
- **Control panel settings not saved** — changes to overlay position, audio on/off,
  volume and signal-sound toggle now persist to `config.json` across restarts.
  Previously only theme changes were saved; all other panel changes were lost on exit.
- **Volume** is now written to `config.json` (with an 800 ms debounce so rapid slider
  moves don't thrash the file).
- **Overlay invisible after monitor switch** — saved `overlay_x`/`overlay_y` coordinates
  are validated against the current screen size on startup. If they fall outside the
  screen (e.g. after switching from a smaller monitor to a larger one), the overlay is
  reset to position `(30, 30)` instead of appearing off-screen.

### Added
- **Setup wizard: multi-monitor support** — the resolution step now lists every
  connected monitor with its physical resolution (via mss, DPI-scaling-independent).
  The largest monitor is pre-selected as the SC gaming display.
- **Setup wizard: automatic resolution detection** — the wizard pre-selects the
  detected monitor and marks it with `← detected`.
- **Setup wizard: new resolution presets** — added `3840 × 1440`, `5120 × 1440`,
  `3840 × 2160` and `5120 × 2160` (5K2K ultrawide). Unrecognised resolutions are
  computed proportionally from the `2560 × 1440` baseline.
- **Setup wizard: scrollable resolution list** — the list is now in a fixed-height
  scrollable frame so the Next button stays visible regardless of monitor count.

## [1.3.1] – 2026-04-19

- V1.0 feature-complete release: control panel, tray icon, hotkey, audio, setup wizard,
  6 themes, ghost theme, position presets, rarity colour coding, sci-fi sounds.
- Full test coverage (430 tests, all modules ≥ 98 %).
- GitHub Actions CI + Release workflow (Inno Setup installer, Tesseract via GitHub API).
