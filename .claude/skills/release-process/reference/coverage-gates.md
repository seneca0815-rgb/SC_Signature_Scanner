# Coverage Gates Reference

## Thresholds

| Module | Gate | Rationale |
|--------|------|-----------|
| `app_state.py` | 100 % | Core shared state, every branch tested |
| `audio_manager.py` | 100 % | WAV loading, volume, winsound fallback |
| `control_panel.py` | 100 % | Full UI acceptance coverage |
| `logger_setup.py` | 100 % | Windows/Linux paths, rotation |
| `tray_icon.py` | 100 % | Run/stop/callbacks/fallback icon |
| `themes.py` | 100 % | Pure data, trivially covered |
| `main.py` | 99 % | `if __name__ == "__main__"` guard excluded |
| `overlay.py` | 98 % | Live-display tkinter drawing excluded |
| `setup_wizard.py` | 98 % | GUI-only branches excluded |
| `overlay_window.py` | 95 % | Some live-draw paths excluded |
| `region_selector.py` | 97 % | Interactive UI excluded |
| **Global gate** | **90 %** | Aggregate across all modules |

## How to check

```powershell
# Quick check (uses existing coverage.xml from last test run)
python scripts/check_release.py --skip-tests

# Full gate (runs tests + coverage)
python scripts/check_release.py

# Drill into a specific module
.venv\Scripts\python -m pytest tests/ --cov=setup_wizard --cov-report=term-missing -q
```

## History

| Version | Total | Notes |
|---------|-------|-------|
| 1.4.4 | ~99 % | All modules at or above individual thresholds |
| 1.4.3 | ~99 % | region_selector tests added |
| 1.3.1 | ~98 % | First full coverage pass (430 tests) |

## Excluded patterns

Configured in `.coveragerc`:
- `if __name__ == "__main__":` guards
- Live tkinter drawing (requires a running display)

## What to do when coverage drops

1. Run `python scripts/check_release.py --skip-tests` to see which module is below gate
2. Run `pytest --cov=<module> --cov-report=term-missing` to see missing lines
3. Typical causes:
   - New code path added without a corresponding test
   - A conditional branch (e.g. `if platform.system() == "Windows"`) only reachable on specific OS
   - Exception handler that's hard to trigger in tests (mock the exception)
4. Add a test, re-run gate, then release
