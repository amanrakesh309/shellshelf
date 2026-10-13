# ShellShelf

A polished local launcher for your shell aliases and simple commands (Linux + macOS).

Browse, search, favorite, and **explicitly** launch your own shortcuts. Shell config files are only ever **read as text** — never sourced, executed, or modified — and imported commands never run automatically.

## Stack

Python 3 standard library only (no installs needed):

- Backend: `http.server` (threaded) + JSON API in `shellshelf/`
- Frontend: dependency-free HTML/CSS/JS in `static/` (no build step, no npm)
- Storage: JSON file in the app's own data dir (see below)
- Tests: `pytest` (preinstalled in this environment)

> Why not Tauri? Tauri was evaluated first (per the plan). It needs Node/npm for the frontend toolchain plus a C linker, `pkg-config`, and WebKitGTK system libs — none of which exist in this environment, and installing them would require network installs / elevated privileges, which are out of scope. Native Tk/GTK is also unavailable (`tkinter` missing, `gi` broken in the sandbox). The stdlib local-web approach runs on Linux and macOS with only `python3`, keeps every gate testable, and is documented here as an explicit limitation (UI opens in your browser rather than a bundled WebView binary).

## Prerequisites

- Python 3.10+ (tested on 3.13)
- `pytest` for tests (`python3 -m pytest --version`)
- A browser (the app opens `http://127.0.0.1:8765/` automatically; use `--no-browser` on headless machines)
- Linux: `xdg-open` for "Open application / file" mode. macOS: `open` (built in).

No `pip install`, no root, no system packages.

## Run locally

```bash
python3 app.py                # serves at http://127.0.0.1:8765/ and opens a browser tab
python3 app.py --port 8080 --no-browser   # headless / custom port
SHELLSHELF_DATA_DIR=/tmp/demo python3 app.py  # isolated data dir (also used by tests)
```

Data file locations:

- Linux: `~/.config/shellshelf/shortcuts.json` (or `$XDG_CONFIG_HOME/shellshelf/`)
- macOS: `~/Library/Application Support/ShellShelf/shortcuts.json`
- Override: `SHELLSHELF_DATA_DIR=/path/to/dir`

## Desktop install (Phase 8)

The app currently runs as a local web app: `python3 app.py` serves the UI and
opens it in your browser. There is no bundled native window yet — building one
(Tauri/Electron/PyInstaller/pywebview) needs toolchains unavailable here (no
Node, C linker, WebKitGTK, or `pip`), so that step stays blocked (see
`plan.md` Phase 8). The smallest distributable that closes part of the gap with
stdlib only:

```bash
python3 packaging/build.py          # builds dist/shellshelf.pyz (single file)
python3 dist/shellshelf.pyz --help  # smoke check (prints help, serves nothing)
python3 dist/shellshelf.pyz         # run from the bundle
```

- Linux: copy `packaging/ShellShelf.desktop` to `~/.local/share/applications/`
  and adjust its `Exec=`/`Icon=` paths to your checkout (or `dist/` location);
  `packaging/icon.svg` is the app icon.
- macOS: `packaging/macos-Info.plist` is a bundle template with py2app
  instructions; until bundled, run `python3 app.py` (or the pyz) — `open -a`
  launching works as-is.

## Install as an app (PWA)

ShellShelf's frontend is installable as a Progressive Web App **where the
browser and OS support it** — installation steps and behavior vary by browser
and OS and are not identical everywhere:

1. Start the backend first (it is required — see below):
   `python3 app.py` (or `python3 dist/shellshelf.pyz`), then open
   `http://127.0.0.1:8765/`.
2. **Chrome / Edge (Linux, macOS, Windows):** open the site, then use the
   install icon in the address bar (or menu → "Install ShellShelf…").
   The app then opens in its own `standalone` window.
3. **Safari (macOS):** open the site, then File → "Add to Dock…" (available in
   recent macOS releases; name and availability differ by version).
4. **Firefox:** desktop Firefox currently offers limited/no PWA installation —
   use ShellShelf as a pinned tab instead.

The service worker caches the app shell (page, CSS/JS, manifest, icons) only.
It never caches shortcut data, API responses, shell file contents, command
output, or errors, and all `/api/*` requests always go to the network.

**Without the Python backend nothing data-driven works:** the installed window
may still render its shell from cache, but the shortcut list, search, import,
and launching all need `http://127.0.0.1:8765/` running — offline use apart
from the cached shell has **not** been tested in a real browser (no browser is
available in this environment), so no offline capability is claimed.

## Core workflow

1. **Add** a shortcut (name + command + launch mode) or **Import** from `~/.zshrc`, `~/.zprofile`, `~/.bashrc`, `~/.bash_profile`, `~/.profile` (zsh first).
2. **Find** it via search (`/` focuses search) or Favorites-only filter.
3. **Open** it to see the exact command and launch explanation, then press **Launch now** — nothing runs before that click. Output and errors appear in the dialog.

## Supported alias syntax (import)

Imported (offered in preview):

```bash
alias ll='ls -la'
alias gs="git status"
alias p=python3
```

Skipped with a per-line reason:

- Not a simple `alias name=value` line (functions, `export`, `if/for/while`, comments, blanks)
- Unbalanced/missing quotes, empty commands, duplicates in the same file
- Anything containing shell metacharacters: `` $ ` ! * ? ~ # ( ) { } [ ] < > | & ; \ `` or sequences `$(`, `${}`, `&&`, `||`, `>>`, `<<`, backticks (command substitution, chaining, redirection, globbing)
- Commands starting with `sudo/doas/su/eval/exec/source` (privileged or evaluating — add manually if you really want them)

Preview always comes before saving; already-saved names are flagged as duplicates and not overwritten. Pasted text works the same as file import.

## Launch behavior

- **Run command** (default): parsed with `shlex.split` and executed via `subprocess.run(argv, shell=False)` with output captured. Arguments are never interpolated into a shell string.
- **Shell syntax needed**: if the command contains shell metacharacters, the API returns HTTP 409 with an explanation and the UI reveals an explicit *"I understand this needs `sh -c`" checkbox. Only after you tick it does the app run `["sh", "-c", command]` — still with `shell=False` (no string interpolation by Python).
- **Open application / file**: URLs and file paths go through the platform opener
  (Linux `xdg-open`, macOS `open`) as a separate argv element. Bare installed-app
  names are now launched properly: Linux resolves them via `PATH`
  (`shutil.which`, actionable error if missing), macOS uses `open -a <name>`.
  On other platforms the target is shown so you can open it manually.
- `POST /api/launch` without `"confirmed": true` returns HTTP 400 — imported commands never run automatically. Timeouts (15 s), missing executables (exit 127), and stderr are all surfaced in the UI. Nothing requests elevated privileges.

## Safety guarantees (reviewed)

- Shell startup files are **read as text only** (`open(...).read()`); the parser uses only string/regex ops — no `eval`, `exec`, `os.system`, `subprocess` with `shell=True`, or sourcing.
- The app writes only to its own data dir (`shortcuts.json` + `.tmp`); it never writes to `~/.bashrc` & co. (covered by `test_import_preview_before_save_and_no_rc_modification`).
- Imported content is treated as untrusted: metacharacters rejected, duplicates flagged, preview required.

## Checks run

```bash
python3 -m py_compile app.py shellshelf/*.py   # OK
python3 -m pytest tests/ -q                    # 27 passed
# Manual: started server, GET / → 200, manifest/sw.js/icons/API → 200 with
# correct content types; rebuilt pyz serves the same routes; import candidates OK
```

Formatter/linter: **blocked** — `black`, `ruff`, and `flake8` are not installed and `pip` is unavailable in this environment, so no formatter/linter could be run. Code follows stdlib style and compiles cleanly; this is recorded in `plan.md`.

## Project layout

- `app.py` — entry point (`--port`, `--no-browser`)
- `shellshelf/model.py` — `Shortcut` dataclass + validation
- `shellshelf/storage.py` — JSON store, CRUD/search/favorites
- `shellshelf/alias_parser.py` — safe text-only alias parser
- `shellshelf/launcher.py` — platform abstraction + argv builder + `run_capture`
- `shellshelf/server.py` — HTTP server + JSON API
- `static/index.html|app.js|styles.css` — accessible launcher UI (labels, skip link, keyboard: `/`, `Enter`, `Esc`)
- `static/manifest.webmanifest|sw.js|icons/` — PWA manifest, shell-only service worker, icons (SVG + PNG)
- `packaging/make_icons.py` — stdlib-only icon generator (no new dependencies)
- `tests/test_{model_storage,alias_parser,launcher,server,pwa}.py` — 27 tests

## Remaining limitations

- UI is a browser tab, not a bundled desktop binary (see Tauri note above).
  A PWA install option is documented above, but real-browser install and
  offline behavior are untested here (no browser in this environment).
- "Open application" just delegates to `xdg-open`/`open`; no process-output capture in that mode.
- No formatter/linter available offline (see above).

## Memory measurements

Method: started `python3 app.py --port <N> --no-browser` as a subprocess and
sampled `VmRSS` from `/proc/<pid>/status`; "normal use" = after adding 20
shortcuts via the API plus a search and a confirmed `echo` launch.

| Component | OS | Condition | Observed |
|---|---|---|---|
| Python backend | Linux (Freedesktop SDK 25.08, Flatpak sandbox) | idle | ~23.5 MiB RSS |
| Python backend | Linux (same) | normal use (20 shortcuts + search + launch) | ~23.6 MiB RSS |
| Python backend | macOS | — | **blocked** (no Mac available) |
| Browser tab / installed PWA window | any | — | **blocked** (no browser in this environment) |

No claim is made about overall or relative memory use beyond these two
backend samples.
