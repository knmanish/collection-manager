# collection-manager

`collect` — a CLI **and** web app for managing a personal collection (watches,
pens, knives, or any categories you define).

## Features

- Add, list, search, **edit**, and remove items
- **Editable categories** (rename propagates to existing items)
- **Multi-currency**: store each item in USD/EUR/INR and toggle the whole
  collection into any of them using **live exchange rates** (cached, with an
  offline fallback)
- **Wishlist** of pieces you're after (priority, estimated price, source link),
  with one-click "promote" into the owned collection
- **Pictures auto-fetched from the web** for items and wishlist entries (with
  manual override)
- Vintage-luxury web UI (Playfair Display + EB Garamond, emerald & gold) with
  three tabs: **My Collection** (showcase), **Manage Collection**, **Wishlist**
- Single local JSON file, written atomically; schema-versioned (v2) with
  automatic migration from older formats

## Install

```bash
pip install -e .
```

## CLI

```bash
collect add "Seiko SKX007" -c watch -b Seiko -a 2023-05-10 -v 150 --currency USD -n "Diver"
collect list
collect list -c watch
collect search seiko
collect edit "Seiko SKX007" --value 175        # by name or id
collect remove "Seiko SKX007"

collect category list
collect category add "fountain pen"
collect category rename pen "writing instrument"
collect category remove knife

collect currency EUR    # set display currency; no arg prints current

collect wishlist add "Rolex Submariner" -c watch -b Rolex -v 12000 -p High
collect wishlist list
collect wishlist promote "Rolex Submariner" -a 2026-06-12 -v 11500   # move into collection
collect wishlist remove "Rolex Submariner"
```

## Web app

```bash
collect-web             # http://127.0.0.1:5000
```

Pages: **Collection** (table, filter, search, add/edit/remove), **Summary**
(stats, breakdown, image cards), **Categories** (manage). The currency toggle in
the header converts all displayed values live.

Set `COLLECT_DEBUG=1` to run Flask in debug mode (off by default).

## Standalone desktop app

Build a single double-click executable (no Python needed to run it):

```powershell
pip install -e ".[package]"
.\build-desktop.ps1            # produces dist\collect.exe (~12 MB)
```

`dist\collect.exe` starts the local server and opens your browser automatically.
It reads/writes the same `~/.collect` data. Works fully offline (live FX rates
and auto-image lookup just fall back when there's no internet).

**Sharing it:** the executable contains no data — each user's collection lives in
their own `~/.collect`. So when you hand `collect.exe` to someone, they start with
a clean, empty collection and a first-run welcome (with an optional "load sample
data" button and a built-in guide at `/help`). To wipe this device before sharing,
use "Clear all data" on the Manage tab, or run `collect reset --yes`.

### Use it from your phone (same Wi-Fi)

Run the app bound to your network, then browse to your computer's IP from the
phone — no hosting required, while your computer is on:

```powershell
$env:COLLECT_HOST="0.0.0.0"; collect-app      # or collect-web
# then on the phone: http://<your-computer-ip>:5000
```

`COLLECT_HOST` (default `127.0.0.1`) and `COLLECT_PORT` (default `5000`) control
the bind address and port.

## Architecture

Layered so each concern can change independently:

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Domain model | `model.py`, `errors.py` | what an item is + validation |
| Persistence | `repository.py` | storage-agnostic interface; JSON impl |
| Services | `service.py` | use cases (add/edit/search/categories/…) |
| Integrations | `currency.py`, `images.py` | live FX rates, web image lookup |
| Adapters | `cli.py`, `web/` | argparse and Flask front-ends |
| Config | `config.py` | paths + persisted settings |

Data lives in `~/.collect/` (override with `COLLECT_HOME`). The legacy
`COLLECT_DB` single-file path is still honored.
