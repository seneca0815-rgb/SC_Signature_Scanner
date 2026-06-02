"""
check_release.py  –  SC Signature Reader pre-release gate

Runs the full test suite with coverage and enforces quality gates before
a release tag is created.  Exit code 0 = all gates pass; 1 = at least
one gate failed.

Usage:
    python scripts/check_release.py [--min-coverage N]   (default: 90)
    python scripts/check_release.py --help
"""

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent

# Modules tracked for coverage (must match CI command)
COVERAGE_MODULES = [
    "app_state",
    "audio_manager",
    "control_panel",
    "logger_setup",
    "main",
    "overlay",
    "overlay_window",
    "region_selector",
    "setup_wizard",
    "themes",
    "tray_icon",
]

TEST_FILES = [
    "tests/test_core.py",
    "tests/test_setup_wizard.py",
    "tests/test_integration.py",
    "tests/test_ui_acceptance.py",
    "tests/test_installer.py",
    "tests/test_audio.py",
    "tests/test_tray_icon.py",
    "tests/test_main.py",
    "tests/test_logger.py",
    "tests/test_region_selector.py",
]

COVERAGE_XML = PROJECT_ROOT / "coverage.xml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cov_flag(module: str) -> str:
    return f"--cov={module}"


def run_tests(min_coverage: int) -> bool:
    """Run pytest with coverage. Returns True if tests pass."""
    cmd = [
        sys.executable, "-m", "pytest",
        *TEST_FILES,
        "-v",
        "--tb=short",
        *[_cov_flag(m) for m in COVERAGE_MODULES],
        "--cov-report=xml:coverage.xml",
        "--cov-report=term-missing:skip-covered",
    ]
    print("\n" + "-" * 60)
    print("RUNNING TESTS")
    print("-" * 60)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def parse_coverage(min_pct: int) -> tuple[bool, list[tuple[str, int]]]:
    """
    Parse coverage.xml and check per-module thresholds.
    Returns (all_pass, [(module, pct), ...]) sorted ascending by pct.
    """
    if not COVERAGE_XML.exists():
        print("ERROR: coverage.xml not found — run tests first")
        return False, []

    tree = ET.parse(COVERAGE_XML)
    root = tree.getroot()

    results: list[tuple[str, int]] = []
    for cls in root.iter("class"):
        name = cls.get("name", "")
        # Strip .py suffix and path separators
        module = Path(name).stem
        if module not in COVERAGE_MODULES:
            continue
        line_rate = float(cls.get("line-rate", "0"))
        pct = round(line_rate * 100)
        results.append((module, pct))

    # Aggregate total
    total_rate = float(root.get("line-rate", "0"))
    total_pct  = round(total_rate * 100)
    results.append(("TOTAL", total_pct))

    results.sort(key=lambda x: x[1])
    all_pass = all(pct >= min_pct for _, pct in results)
    return all_pass, results


def check_version_consistency() -> bool:
    """Verify that main.py and SCSigReader.iss report the same version."""
    main_py = PROJECT_ROOT / "main.py"
    iss     = PROJECT_ROOT / "SCSigReader.iss"

    version_main = None
    version_iss  = None

    for line in main_py.read_text(encoding="utf-8").splitlines():
        if line.startswith("VERSION"):
            version_main = line.split('"')[1]
            break

    for line in iss.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#define AppVersion"):
            version_iss = line.split('"')[1]
            break

    print("\n" + "-" * 60)
    print("VERSION CONSISTENCY")
    print("-" * 60)
    print(f"  main.py       : {version_main}")
    print(f"  SCSigReader.iss: {version_iss}")

    if version_main != version_iss:
        print("  [FAIL]  MISMATCH -- update both files to the same version")
        return False
    print("  [PASS]  OK")
    return True


def print_coverage_report(results: list[tuple[str, int]], min_pct: int, all_pass: bool):
    print("\n" + "-" * 60)
    print(f"COVERAGE GATE  (threshold: {min_pct}%)")
    print("-" * 60)
    for module, pct in results:
        icon = "PASS" if pct >= min_pct else "FAIL"
        bar  = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  [{icon}] {module:<22} {bar}  {pct:3}%")
    print()
    if all_pass:
        print("  [PASS]  All modules meet the coverage gate")
    else:
        below = [f"{m} ({p}%)" for m, p in results if p < min_pct]
        print(f"  [FAIL]  Below threshold: {', '.join(below)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pre-release quality gate")
    parser.add_argument("--min-coverage", type=int, default=90,
                        metavar="N", help="Minimum coverage %% (default: 90)")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip test run, only check existing coverage.xml")
    args = parser.parse_args()

    gates: dict[str, bool] = {}

    # 1. Tests
    if not args.skip_tests:
        gates["tests"] = run_tests(args.min_coverage)
    else:
        print("(skipping test run — using existing coverage.xml)")
        gates["tests"] = True

    # 2. Coverage
    cov_pass, results = parse_coverage(args.min_coverage)
    print_coverage_report(results, args.min_coverage, cov_pass)
    gates["coverage"] = cov_pass

    # 3. Version consistency
    gates["version"] = check_version_consistency()

    # Summary
    print("\n" + "=" * 60)
    print("RELEASE GATE SUMMARY")
    print("=" * 60)
    all_pass = True
    for gate, passed in gates.items():
        icon = "[PASS]" if passed else "[FAIL]"
        print(f"  {icon}  {gate}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n  [PASS]  All gates passed -- ready to release")
    else:
        print("\n  [FAIL]  One or more gates failed -- fix before releasing")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
