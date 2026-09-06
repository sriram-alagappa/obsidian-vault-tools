# Obsidian Vault Tools

Local, offline tooling that makes an Obsidian vault's **screenshots searchable** and keeps its
**attachments tidy**.

Built 2026-09-06 for the `My Vault` Obsidian vault, which held 144 notes and 486
screenshots — where most of the actual content lived inside the images, unsearchable.

## What it does

Three layers, only the first two of which are automated:

| Layer | What | Count (at build time) | Maintained by |
|---|---|---|---|
| Notes | your `.md` files | 144 | you |
| **`_OCR/`** | one `.ocr.md` sidecar per image, with extracted text | 483 | **this tooling, automatically** |
| **`_Summaries/`** | one prose summary per folder | 37 | an LLM, on demand |

OCR runs entirely on-device using Apple's Vision framework. **No network, no API key, no cost.**
A full pass over 488 images takes ~70 seconds.

## Quick start

```bash
./build.sh                                    # compile the Swift OCR binary (needs Xcode)
export OBSIDIAN_VAULT="/path/to/Your Vault"   # the folder whose children are your notes
python3 scripts/build_ocr.py                  # OCR everything; idempotent
```

That's it. Re-run any time — it only processes new or changed images, reaps sidecars whose
image is gone, and leaves everything else alone.

## The scripts

| Script | Purpose |
|---|---|
| `build.sh` | Compiles `src/ocrshot.swift` → `bin/ocrshot` |
| `scripts/build_ocr.py` | Walks the vault, OCRs images, writes `_OCR/**.ocr.md`, reaps orphans |
| `scripts/tidy_attachments.py` | Files each image next to the note that embeds it. **Dry-run by default** |
| `scripts/corpus.sh` | Dumps one folder's notes + OCR text, for reading or summarising |
| `scripts/write_summary.py` | Stamps frontmatter + digest onto a summary body and files it |

## Documentation

- **[docs/RUNBOOK.md](docs/RUNBOOK.md)** — set-up on a new machine, day-to-day commands, the macOS and network gotchas
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how each piece works and why it's built that way
- **[docs/HISTORY.md](docs/HISTORY.md)** — what was done on 2026-09-06 and what was learned

## Requirements

- macOS (Apple Vision framework)
- Xcode or Command Line Tools with Swift 5+
- Python 3.9+
- If the vault lives in iCloud: **Full Disk Access** for whatever runs these scripts

## Status

Working and in production against the live vault. Not yet automated — see
[RUNBOOK § Not yet done](docs/RUNBOOK.md#not-yet-done).
