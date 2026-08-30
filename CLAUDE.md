# CLAUDE.md

Magic Zebra Printer is a Python CLI that auto-sizes a PDF or image for
printing on a Zebra label printer (continuous roll paper) via CUPS. It scales
content to a fixed width, rotates landscape pages to portrait, computes the
required page length, and sends the result to a printer whose name contains
"zebra". See [README.md](README.md) for the user-facing description,
installation, and usage — keep it current with any behavior change; don't
duplicate it here.

## Running the test suite

```bash
python3 -m venv venv   # once
venv/bin/pip install -r requirements.txt
./test_magic_zebra_printer.py
```

Requires `imagemagick` and `ghostscript` on PATH (see README for install
commands) since one test converts an image input. `lp`/`lpstat` (from
`cups-client`) must also be importable even though no test prints — `sh`
resolves them at import time in `magic-zebra-printer.py`.

## Conventions

- Tests never invoke UI paths or spawn GUI dialogs. All test/dev runs pass
  `-noprint` as the second argument so nothing is sent to a real printer and
  no drag-and-drop / dialog code executes. Any verification of
  notification/dialog code is done by stubbing the underlying `sh` commands,
  never by actually launching a GUI.
- Fail early and loudly: no silent fallbacks or swallowed exit codes.
  `test_magic_zebra_printer.py` exits nonzero on any test failure.
- The 6mm right-margin and 10cm content-width constants
  (`CONTENT_WIDTH_CM`, `RIGHT_MARGIN_CM`) live at the top of
  `magic-zebra-printer.py`.
