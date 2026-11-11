# StatCraft v117.0.0 Milestone Plan: Direct `.xlsx` Import, Guided Onboarding & Sample Library, Crash Dialog with GitHub Link, & Docs/CI Sync

> **For agentic workers:** Executed under `superpowers:writing-plans`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. Every feature/fix must first fail in `tests/test_phase12_v117_onboarding_xlsx_crash.py` (RED), be implemented cleanly (GREEN), and pass the entire `unittest discover tests` suite before release.

**Goal:** Deliver `v117.0.0` with first-time onboarding polish (fixing the faint gray Welcome sample link, adding a 4-dataset Sample Library + 5-step Interactive Quick Tour), zero-dependency Excel `.xlsx` import, an air-gap-safe Crash Dialog with pre-filled GitHub Issue link + `.github/ISSUE_TEMPLATE/bug_report.yml`, `README.md` sync, and a clean full `2,200+` test verification run.

---

## Architecture & Modules

1. **Direct Excel `.xlsx` Reader (`statcraft/xlsx_import.py`, `statcraft/app.py`, `statcraft/modern_app.py`)**
   - `load_xlsx(path, sheet_name=None, has_header=True, column_types=None)` reads `.xlsx` workbooks using stdlib `zipfile` + `xml.etree.ElementTree` (zero external dependencies; supports shared strings, inline strings, booleans, Excel serial dates via `numFmtId`/`s` style inspection, formula cached values `<v>`, missing empty cells, and bounded `MAX_CELLS`/`MAX_TOTAL_BYTES` safety checks).
   - Single-sheet `.xlsx` loads directly as active `Worksheet`; multi-sheet `.xlsx` loads via `mpx_create.create_project(sheets)` with `statcraft_owned = True` so all sheets appear in the Navigator.
   - Wired into `Presenter.load`, `ModernWindow.open_document` filter, and CLI/error messaging.

2. **Interactive Sample Library, Fixed Welcome Card & Guided Onboarding Tour (`statcraft/onboarding.py`, `statcraft/modern_app.py`)**
   - Replace flat `#64748b` gray links in `WelcomeWatermarkWidget` with high-contrast Quick Start action buttons + sample launcher cards so beginners immediately see interactive buttons instead of dead gray text.
   - `SAMPLE_DATASETS` catalog (`chemical_process`, `six_sigma_shafts`, `wafer_defects`, `reliability_motors`), `SampleLibraryDialog`, and `GuidedTourDialog` (5-step interactive onboarding dialog linked from Welcome Card & `Help > Interactive Quick Tour…`).
   - Fix `ModernWindow.load_connect_sample()` (and shared `load_sample_dataset(key)`) to cleanly reset project/history/dirty state, populate the worksheet, switch focus appropriately, and run an initial starter analysis cleanly.

3. **Crash Recovery Dialog & Pre-Filled GitHub Issue Link (`statcraft/crash_dialog.py`, `statcraft/__main__.py`, `.github/ISSUE_TEMPLATE/bug_report.yml`)**
   - Strictly **no** background telemetry or auto-reporting (100% compliant with `airgap_verifier.py`).
   - On an unhandled exception via `install_crash_hook()`, write scrubbed diagnostics to `last_crash.log` and show `CrashReportDialog` with **Copy Crash Details** and **Report Issue on GitHub…** (opening `https://github.com/SkinnDeep/StatCraft/issues/new?title=...&body=...&labels=bug` in the user's browser via `QDesktopServices.openUrl`).

4. **Documentation, Version Sync & Full Suite Verification (`v117.0.0`)**
   - Update `README.md` (`v115.0.0` -> `v117.0.0`, full feature catalog, Excel `.xlsx` import, Guided Tour, Sample Library, Crash Dialog).
   - Bump `116.6.0` -> `117.0.0` across all 7 version metadata files + Phase 5 & Phase 6 tests.
   - Run full `python -m unittest discover tests` (`2,200+` tests) + `tests/test_phase12_v117_onboarding_xlsx_crash.py`, tag `v117.0.0`, and push to `origin`.
