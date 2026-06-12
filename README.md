# collection-manager

`collect` — a CLI **and** web app for managing a personal collection (watches,
pens, knives, or any categories you define).

## Features

- Add, list, search, **edit**, and remove items
- **Editable categories** (rename propagates to existing items)
- **Multi-currency**: store each item in USD/EUR/INR and toggle the whole
  collection into any of them using **live exchange rates** (cached, with an
  offline fallback)
- **Interactive summary page** with value-by-category breakdown and item cards,
  including **pictures auto-fetched from the web** (with manual override)
- Single local JSON file, written atomically; schema-versioned with automatic
  migration from older formats

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
```

## Web app

```bash
collect-web             # http://127.0.0.1:5000
```

Pages: **Collection** (table, filter, search, add/edit/remove), **Summary**
(stats, breakdown, image cards), **Categories** (manage). The currency toggle in
the header converts all displayed values live.

Set `COLLECT_DEBUG=1` to run Flask in debug mode (off by default).

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
