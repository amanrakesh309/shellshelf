# ShellShelf Development Plan

## Project goal

Build a polished desktop app for Linux and macOS that lets users browse, search, organize, and explicitly launch their own shell aliases and simple commands.

The app must import only straightforward alias declarations from shell configuration files. It must never source or execute those files, modify them, or automatically run imported commands.

## Phase 1 — Inspect and plan

**Tasks**
- Inspect the repository, existing conventions, and available development tools.
- Choose a cross-platform desktop stack. Prefer Tauri if the environment supports it; otherwise explain the alternative.
- Identify the app’s target platforms, dependencies, and any environment limitations.
- Record the proposed architecture and implementation steps.

**Gate checks — all must pass before Phase 2**
- The existing repository and toolchain have been inspected.
- The chosen stack is justified and supports the intended Linux/macOS scope, or its limitations are documented.
- A concise architecture and implementation plan is recorded.
- No dependencies have been installed without authorization.

## Phase 2 — App skeleton and design

**Tasks**
- Set up the application using the chosen stack.
- Create a compact, accessible launcher layout.
- Add navigation or views for the shortcut list, adding/editing shortcuts, and settings or import.
- Implement loading, empty, and error states.

**Gate checks — all must pass before Phase 3**
- The app starts using documented development instructions.
- The main UI renders without errors.
- The layout supports keyboard navigation and has clear labels.
- Empty and error states are present.
- No placeholder UI is presented as completed functionality.

## Phase 3 — Shortcut model and storage

**Tasks**
- Define a shortcut model with a friendly name, command, source, optional description, launch mode, and favorite state.
- Store shortcuts in the app’s own configuration or data file.
- Implement add, edit, delete, search, and favorite operations.
- Validate required fields and provide clear user feedback.

**Gate checks — all must pass before Phase 4**
- Shortcuts persist across app restarts.
- Add, edit, and delete operations work.
- Search and favorites work.
- Invalid or incomplete entries are rejected with understandable messages.
- Unit tests cover storage and shortcut validation.

## Phase 4 — Safe alias import

**Tasks**
- Support importing simple aliases from `~/.bashrc` and `~/.zshrc`, plus relevant macOS shell configuration files.
- Parse only straightforward declarations, such as `alias ll='ls -la'`.
- Show a preview and let users select which entries to import.
- Explain why unsupported or malformed lines are skipped.
- Treat all imported content as untrusted.

**Must not**
- Source or execute any shell configuration file.
- Import shell functions, conditionals, command substitutions, or arbitrary shell code as executable entries.
- Modify shell configuration files.

**Gate checks — all must pass before Phase 5**
- Import shows a preview before saving entries.
- Only supported, straightforward aliases are imported.
- Unsupported and malformed lines are skipped and explained.
- Importing does not modify shell configuration files.
- Tests cover single and double quotes, malformed declarations, duplicates, and shell metacharacters.
- Tests confirm parsing never executes imported content.

## Phase 5 — Command and application launching

**Tasks**
- Implement separate launch modes for running a command in a terminal and launching an application.
- Handle Linux and macOS behavior behind a small, testable platform abstraction.
- Show the command and require an explicit user action before launching.
- Display command output and errors where supported.
- Prefer process APIs that pass executable arguments separately rather than interpolating shell strings.
- If shell syntax is required, make that behavior explicit and explain it in the UI.

**Gate checks — all must pass before Phase 6**
- Imported commands never run automatically.
- The user sees what will run and explicitly confirms or clicks to launch it.
- Linux and macOS launch behavior is implemented or unsupported behavior is clearly documented.
- Errors are surfaced to the user.
- Tests cover command construction and ensure arguments are not accidentally interpolated into a shell string.
- The app does not request elevated privileges.

## Phase 6 — Integration and quality

**Tasks**
- Connect the UI, storage, import, and launching features.
- Add keyboard navigation and accessible labels throughout the main workflows.
- Review input validation, error handling, and security-sensitive code.
- Run the project’s tests, formatter, and linter; fix issues.

**Gate checks — all must pass before Phase 7**
- The complete core workflow works: add or import a shortcut, find it, and launch it explicitly.
- Tests pass.
- Formatter and linter pass, or any environment limitation is documented.
- No known crash or unhandled error blocks the core workflow.
- A review confirms shell startup files are not executed or modified.

## Phase 7 — Documentation and release readiness

**Tasks**
- Write a README with prerequisites, development instructions, run/build commands, and Linux/macOS notes.
- Document supported alias syntax and import limitations.
- Document platform-specific launch limitations and any checks that could not be run.
- Summarize the implementation and remaining work.

**Gate checks — phase complete when**
- A new contributor can follow the README to run the app.
- Build instructions and prerequisites are documented.
- Alias-import limitations and safety behavior are clearly explained.
- The final summary lists key files, checks run, and outstanding limitations.

## Phase 8 — Desktop-app gap closure (smallest safe step)

**Context (review 2026-10-13, code inspected before any behavior change)**
- Current app is a local web app: `app.py` serves `http.server` and calls
  `webbrowser.open()` — there is no native desktop window, no app identity
  (icon, `.desktop` entry, `Info.plist`), and no distributable artifact.
- A true bundled window/package (Tauri/Electron/PyInstaller/pywebview) cannot be
  built or tested in this environment: no Node/npm, no C linker/`pkg-config`/
  WebKitGTK, no `pip` for new dependencies, and installing them would need
  network access / elevated privileges (out of scope). That full packaging step
  stays BLOCKED and documented.
- App-launch gap (read in `shellshelf/launcher.py:48-71`,
  `shellshelf/server.py:176-184`): `app` mode always builds
  `["xdg-open", cmd]` (Linux) / `["open", cmd]` (macOS, without `-a`).
  That reliably opens only URLs/files/paths via MIME handlers; bare installed-app
  names do NOT reliably launch (`xdg-open firefox` treats the name as a path;
  macOS needs `open -a <AppName>`). So current behavior "only opens targets
  through xdg-open/open" — confirmed by reading; live GUI launching is not
  verifiable in this headless sandbox.

**Tasks**
- Fix `app`-mode spec construction (stdlib only, still explicit-confirm only):
  classify the target as URL / existing-or-absolute path / bare app name.
  Linux: URLs and paths → `xdg-open`; bare names → resolve via `shutil.which`
  and launch the resolved executable, else return an actionable error.
  macOS: bare app names → `open -a <name>`; URLs/paths → plain `open`.
  Terminal mode and all safety behavior stay unchanged.
- Extend unit tests for the new specs (URL vs path vs app name, per platform);
  keep every existing test and safety requirement intact.
- Add stdlib-only desktop integration: `python -m zipapp` distributable,
  Linux `ShellShelf.desktop` entry + icon, macOS bundle notes; document in README.
- Run the full existing suite plus new tests; run the zipapp build + `--help`
  smoke check.

**Must not**
- Source or execute shell startup files; modify them; automatically run imported
  commands; request elevated privileges; silently install dependencies.

**Gate checks — phase complete when**
### Phase 8 — Desktop-app gap closure (completed 2026-10-13)- App-launch fix (`shellshelf/launcher.py: build_app_spec`): URLs/paths still go
  through `xdg-open` (Linux) / `open` (macOS); bare names now resolve via
  `shutil.which` on Linux (actionable `ValueError` when missing) and use
  `open -a <name>` on macOS. Spec-time work is PATH lookup + stat only — no
  execution; terminal mode, confirmation flow, and `shell=False` unchanged.
- New tests: PATH resolution, unknown-name error, URL/path opener behavior,
  macOS `-a` (in `tests/test_launcher.py`); zip-fallback static serving
  (in `tests/test_server.py`). Existing `test_app_modes_per_platform` still passes.
- Distributable (stdlib only): `__main__.py` + `packaging/build.py` produce
  `dist/shellshelf.pyz`; `server.read_static_bytes` falls back to reading
  `static/*` from inside the zip so the bundle fully serves the UI.
- Desktop integration: `packaging/ShellShelf.desktop` (+ comments to adjust
  paths), `packaging/icon.svg`, `packaging/macos-Info.plist` (template with
  py2app notes); README gained Desktop + updated launch-behavior sections.
- Gate checks (all actually run):
  - Bare-name specs per platform — PASS (4 new unit tests).
  - URL/path opener behavior preserved — PASS (tests).
  - Full suite `python3 -m pytest tests/ -q` → 22 passed (17 existing + 5 new).
  - `python3 packaging/build.py` → built 53 KB pyz, no stray entries; `--help`
    smoke → exit 0; booted pyz serves `GET /` → 200, `/static/app.js` → 200,
    `/api/shortcuts` → `{"shortcuts": []}` — PASS. (One earlier probe failed
    with connection-refused due to a shell job-control artifact in the check
    command itself; re-ran cleanly — PASS.)
  - Desktop entry keys (`Name/Exec/Icon/Type/Categories/Terminal`) — PASS via
    key-presence check; `desktop-file-validate` BLOCKED (not installed, no pip).
  - Live GUI app launching on Linux/macOS — BLOCKED (headless Flatpak sandbox,
    no macOS host; `xdg-open` here proxies to the host). Remains to verify on a
    real desktop: bare-name launch (e.g. calculator), `open -a` on macOS, and
    `.desktop` install flow.
  - Safety re-audit — PASS (no `shell=True`, no `os.system`/`eval`, confirmation
    still required, spec uses `which`/stat only). No dependencies installed, no
    elevated privileges requested.

### Follow-up change (2026-10-13, per user request)
- Import UI no longer shows skipped-lines data: removed the "Skipped lines"
  section from the import dialog (`static/index.html`, `static/app.js`,
  `static/styles.css`). The parser and `/api/import/preview` still classify and
  return skipped lines internally (existing tests + Phase 4 safety gates rely on
  it), but the UI only lists importable entries.
- Shell configuration selection is now zsh-first: `CANDIDATE_FILES` reordered to
  `~/.zshrc`, `~/.zprofile`, `~/.bashrc`, `~/.bash_profile`, `~/.profile`, so the
  dropdown defaults to zsh. README updated.
- Checks: `pytest` → 22 passed; live probe confirmed candidate order
  (Zsh first) and no skipped-lines markup in served UI.

## Phase 9 — Installable PWA on the existing Python backend (stdlib only)

**Context (review 2026-10-13; Python backend + safety behavior preserved, no
Tauri/desktop wrapper)**
- The frontend (`static/index.html|app.js|styles.css`) is dependency-free, so it
  can become installable where browsers support PWAs with only static additions:
  a web app manifest, icons, and an optional service worker.
- The Python server stays the required local backend for shortcuts and launching.
  `serve()` already binds `127.0.0.1` only; this phase keeps it that way and adds
  a regression check. Shell-launching APIs must never be exposed to the LAN.

**Tasks**
- Add `static/manifest.webmanifest` (name, short name, icons, theme/background
  colors, `standalone` display, `start_url`/`scope` `/`) and link it from
  `index.html` with `theme-color` and `apple-touch-icon` meta/links.
- Add icons: `static/icons/icon.svg` (+ reuse of the `$ _` motif),
  `icon-192.png`, `icon-512.png`, `apple-touch-icon.png (180)`, generated by a
  committed stdlib-only script (`packaging/make_icons.py`, no new dependencies).
- Serve new types from the backend: `.webmanifest` → `application/manifest+json`,
  plus `.png`/`.svg`; allow `static/icons/*` subpaths with traversal guard;
  serve the worker at `/sw.js` (root scope) from `static/sw.js`.
- Add `static/sw.js` caching **app-shell files only**
  (`/`, `/index.html`, CSS/JS, manifest, icons). `GET /api/*`, non-GET, and
  cross-origin requests stay network-only; no `cache.put` of responses anywhere,
  so shortcut data, shell contents, outputs, and errors are never cached.
  Register it from `app.js` guarded and non-blocking.
- Add tests: manifest validity + icon serving/dimensions, SW served with JS type
  and API-bypass/no-`cache.put` behavior, loopback bind (`127.0.0.1`, no
  `0.0.0.0` in server code). Keep all existing tests green.
- Measure backend idle/normal-use RSS on Linux via `/proc` (stdlib `resource`
  or `/proc/<pid>/status`); record method/OS/values in README/`plan.md`.
  macOS and browser-memory checks are expected BLOCKED here (no Mac, no browser).
- Document: backend-first start, per-browser install steps (Chrome/Edge, Safari,
  Firefox-limits) with "support varies" wording; what needs the backend; no
  offline-work claim unless tested in a real browser.

**Must not**
- Source/execute/modify shell startup files; auto-run imported commands; weaken
  confirmation/import safety checks; install dependencies; request elevated
  privileges; bind non-loopback; cache API/user data in the worker.

**Gate checks — phase complete when**
- [ ] Manifest + icons valid and served (correct content types, PNG dimensions).
- [ ] App loads and shortcut/API workflows still work (suite + live boot probe).
- [ ] Existing tests pass; new manifest/static/SW/loopback tests pass.
- [ ] Backend listens only on loopback (test + code audit).
- [ ] Service worker does not cache API or user data (behavior test).
- [ ] `py_compile` + `pytest` + zipapp rebuild + pyz smoke pass; formatter/linter
  reported honestly (expected blocked: no black/ruff/flake8, no pip).
- [ ] Memory method + Linux values recorded; macOS/browser marked blocked.
- [ ] README covers backend start, install steps with varies-by-browser wording,
  backend-required limits, and no untested offline claim.

### Phase 9 — results (completed 2026-10-13, all checks actually run)
- Manifest + icons: `static/manifest.webmanifest` (name/short name/standalone/
  theme+background `#101418`, 3 icons) served as `application/manifest+json`;
  `icon-192/512.png` IHDR dimensions verified, `apple-touch-icon.png` 180x180,
  `icon.svg` as `image/svg+xml` — PASS. Icons generated by committed stdlib-only
  `packaging/make_icons.py` (no new dependencies).
- App loads + workflows intact: `GET /`, `/sw.js`, manifest, icons, `/api/*`
  → 200 with correct types, live boot probe; full suite `pytest` → 27 passed
  (22 existing + 5 new PWA tests) — PASS.
- Loopback: `serve()` binds `127.0.0.1` (test) + audit finds no `0.0.0.0` in
  server/app/build code — PASS. No `--host` option added, so the launch APIs
  cannot be exposed to the LAN from this codebase.
- Worker safety: `/sw.js` served as JS; source test confirms `/api/` bypass,
  zero `cache.put`, and `SHELL_ASSETS` holds shell paths only — PASS.
- Safety preserved: confirmation/import behavior untouched; re-audit PASS.
- Build/smoke: `py_compile` OK; `packaging/build.py` → 62 KB pyz; booted pyz
  serves `/sw.js`, manifest, icons — PASS. Formatter/linter BLOCKED (no
  black/ruff/flake8, no pip — same as Phase 6).
- Memory: Linux backend idle ~23.5 MiB / normal-use ~23.6 MiB RSS (`/proc`
  VmRSS sampling; method + OS recorded in README). macOS backend and any
  browser/PWA-window memory — BLOCKED (no Mac, no browser here); no low-memory
  claims made.
- Offline: NOT claimed — shell-only caching is implemented but untested in a
  real browser (none available); README states the backend is required for all
  data/launching. Real-browser install flow (Chrome/Edge/Safari/Firefox) also
  untested — BLOCKED, documented with varies-by-browser wording.
- Files changed/added: `static/manifest.webmanifest|sw.js|icons/*`,
  `static/index.html` (manifest/theme/touch-icon links), `static/app.js`
  (guarded SW registration), `shellshelf/server.py` (types, `icons/` subpaths
  with unquote+resolve traversal guard, `/sw.js` root route),
  `packaging/make_icons.py`, `tests/test_pwa.py`, `README.md`.

Work phase by phase. Delegate a phase to a separate agent or subtask when useful, but give each delegate that phase’s tasks and gate checks. A phase is not complete until its gate checks pass.

After each phase:
1. Report what was completed.
2. Report the results of every gate check.
3. Fix any failed checks before proceeding.
4. Update this file if implementation decisions or limitations change.

Do not begin a later phase while the current phase has failing gate checks. Do not claim a check passed unless it was actually run and its result is known.

## Progress log

### Phase 1 — Inspect and plan (completed 2026-10-13)
- Repo inspected: empty repo (only `plan.md`, no commits, no existing code/conventions).
- Toolchain observed (commands actually run):
  - `python3 --version` → Python 3.13.15; `python3 -m pytest --version` → pytest 9.1.1 available.
  - `node`/`npm` → NOT found; `pip3` → NOT found; `tkinter` → NOT available (`ModuleNotFoundError`).
  - `cargo/rustc 1.99.0` present but no `gcc`, no `pkg-config`, no `webkit2gtk`, only `libgtk-3`, `libsoup-3.0` runtime libs; `gi.require_version` broken in sandbox.
  - OS: Linux (Flatpak sandbox, `DISPLAY=:0`, `xdg-open` present, no bundled browser).
- Stack decision: Tauri NOT suitable — it needs Node/npm for the frontend toolchain plus Rust system deps (C linker, pkg-config, WebKitGTK) which are absent, and installing them would need network installs / elevated privileges, which are out of scope. GTK/Tk native Python GUIs are also unavailable (no tkinter, broken gi).
- Chosen alternative: Python 3 standard-library only — `http.server` (threaded) backend + dependency-free HTML/CSS/JS frontend (no build step) + JSON data file + `subprocess` launcher with argv separation. Runs on Linux and macOS with only `python3`; `pytest` (already present) for tests. Documented limitation: UI is a local web app opened in the user's browser (not a bundled WebView binary), which preserves the launcher workflow without new installs.
- Architecture: `shellshelf/{__init__,model,storage,alias_parser,launcher,server}.py` + `static/{index.html,app.js,styles.css}` + `tests/test_*.py` + `app.py` entry + `README.md`. Data file: XDG `~/.config/shellshelf/shortcuts.json` on Linux, `~/Library/Application Support/ShellShelf/shortcuts.json` on macOS, overridable via `SHELLSHELF_DATA_DIR` for tests.
- Gate checks: inspected ✓ / stack justified with limitations ✓ / architecture recorded here ✓ / no dependencies installed ✓ (nothing installed).

### Phase 2 — App skeleton and design (completed 2026-10-13)
- Built stdlib stack: `app.py` + `shellshelf/server.py` + `static/index.html|app.js|styles.css`. Views: shortcut list, add/edit dialog, detail/launch dialog, import dialog (file candidates + paste + preview).
- States: loading indicator, empty state with actions, error/notice banners (`role=alert/status`).
- Gate checks (all actually run): `GET /` → 200; `GET /api/shortcuts` → `{"shortcuts": []}`; `GET /api/import/candidates` OK (server started with `timeout 12 python3 app.py --port 18765 --no-browser`); static audit script confirmed labels/skip-link/aria/Enter/Escape/tabindex and no TODO placeholders — all PASS. No placeholder presented as done (every button wired to a real API call).

### Phase 3 — Shortcut model and storage (completed 2026-10-13)
- `shellshelf/model.py` (name/command/source/description/launch_mode/favorite + validation) and `shellshelf/storage.py` (own JSON data file, CRUD/search/favorites, duplicate-name guard, corrupt-file tolerant).
- Gate checks: persistence verified by `test_add_and_persist_across_restarts` (reload from same dir); CRUD/search/favorites by `test_crud_search_favorites`; invalid rejected by `test_validation_rejects_bad_entries`; suite `tests/test_model_storage.py` — PASS (`pytest`: 17 passed).

### Phase 4 — Safe alias import (completed 2026-10-13)
- `shellshelf/alias_parser.py` reads files as text only; supports `alias n='v'` / `"v"` / bare token; rejects metachars, substitutions, chaining, redirection, `sudo/eval/...`; preview (`POST /api/import/preview`) → explicit select → confirm (`POST /api/import/confirm`); per-line skip reasons; duplicates flagged.
- Never sources/executes/modifies rc files (no `subprocess`/`eval`/`exec`/`os.system` in parser; storage writes only to `shortcuts.json`).
- Gate checks: preview-before-save, straightforward-only, skip reasons, read-only (file-content-equality assertion), and `tests/test_alias_parser.py` (quotes, malformed, duplicates, metachars, functions/conditionals, no-exec canary + source audit) — all PASS.

### Phase 5 — Command and application launching (completed 2026-10-13)
- `shellshelf/launcher.py`: `build_launch_spec` (argv separation via `shlex.split`; `sh -c` only when shell syntax detected, flagged `needs_shell` + explanation), Linux `xdg-open` / macOS `open` app mode, `run_capture(shell=False)` with timeout; `POST /api/launch` requires `confirmed=true` (400 otherwise), 409 + ack checkbox when shell needed; UI detail dialog shows exact command + explanation + output/stderr.
- Gate checks: no auto-run (test posts without confirm → 400); explicit confirm + visible command (UI + API test); Linux/macOS argv covered by `test_app_modes_per_platform`, other platforms show manual fallback; errors surfaced (127/timeout/stderr paths); argv-no-interpolation tests PASS; source audit confirms no `shell=True` subprocess, no `sudo/pkexec/osascript` — PASS. No elevated privileges requested.

### Phase 6 — Integration and quality (completed 2026-10-13)
- Full workflow test `test_full_workflow_add_find_launch_explicitly` (add → search → rejected unconfirmed launch → confirmed launch with output) — PASS. Keyboard (`/`, Enter, Esc, tab order) + aria labels throughout; validation/error paths reviewed; rc-file safety re-audited (writes only under data dir).
- Checks run: `python3 -m py_compile app.py shellshelf/*.py` → OK; `python3 -m pytest tests/ -q` → 17 passed.
- Formatter/linter: BLOCKED — `black`/`ruff`/`flake8` not installed and `pip` unavailable in sandbox, so nothing could be run; code kept stdlib-styled and compile-clean. No known crash blocks the core workflow.

### Phase 7 — Documentation and release readiness (completed 2026-10-13)
- Wrote `README.md` (prereqs, `python3 app.py` run commands, data-dir locations, Linux/macOS launch notes, supported alias syntax + skip rules, safety behavior, checks run, limitations).
- Gate checks: README run instructions verified (server boot + API probes above); build needs nothing beyond Python; import limitations + safety + unverifiable checks (formatter/linter) explicitly documented; this log plus final summary list files/checks/limitations.

