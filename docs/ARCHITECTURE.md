# Architecture

How each piece works, and why it's built the way it is.

---

## `src/ocrshot.swift` — the OCR engine

A single Swift file compiled to a self-contained binary. Takes image paths as arguments, emits
one JSON object per line on stdout.

```bash
bin/ocrshot [--langcorrect] [--no-columns] [--strategy gutter|leftedge]
            [--gutter N] [--line-tol F] [--min-conf F]  image1.png image2.png ...
```

### Recognition

Apple's `VNRecognizeTextRequest` at `.accurate`, English, via a `VNImageRequestHandler`.
Images decode through ImageIO — no AppKit dependency.

### Line assembly — the part that took the work

Vision returns text observations with bounding boxes, not lines. Reconstructing readable text
from those boxes is where naive OCR falls apart on UI screenshots.

**First attempt — group by vertical position.** Works on single-pane captures. Fails badly on
multi-panel UIs: a Figma window has four columns sharing every horizontal band, so a sentence
in the comment thread gets shredded with sidebar labels.

**Second attempt — gutter detection.** Look for x-ranges with no text at all, split there.
*Never fired.* Dense UIs have text at virtually every horizontal position; even a 0.8%-wide
empty band doesn't exist.

**What works — left-edge clustering.** UI panels are left-aligned at distinct x positions.
Collect every observation's `minX`, sort, and split wherever the gap between consecutive values
exceeds a threshold (default **8%** of width). Assign observations to columns by midpoint, then
group into lines *within* each column and emit columns left to right.

The result adapts on its own: single-pane screenshots detect one column and pass through
unchanged; a dense dashboard detects six. In the 488-image corpus the distribution came out
133 images at 1 column, 85 at 2, 101 at 3, 80 at 4, 51 at 5, 26 at 6.

### Noise filtering

- Observations below `--min-conf` (default **0.30**) are dropped
- Lines under 2 characters, or containing no alphanumerics at all, are dropped

Both thresholds are deliberately conservative. A test at `--min-conf 0.5` removed real junk
(`a мюi`, `Ml todolet`) but also removed a legitimate Figma URL — exactly the kind of string
you'd search for. Confidence filtering is a blunt instrument; the line-level filter does the
useful work.

### Concurrency

`DispatchQueue.concurrentPerform` across the input paths, with a lock around result collection
and ordered output. ~70 seconds for 488 images.

---

## `scripts/build_ocr.py` — the driver

### Sidecar format

```
_OCR/<same path as image>/<image name>.ocr.md
```

```yaml
---
source: "Pasted image 20260814110113.png"   # filename only — see below
image_width: 2648
image_height: 1382
ocr_confidence: 1
ocr_chars: 69
ocr_columns: 1
ocr_date: 2026-09-06
ocr_engine: apple-vision
tags: [ocr]
referenced_in:
  - "[[Weekly Notes]]"
---

![[Pasted image 20260814110113.png]]

## Extracted text
…
```

### Why bare filenames, not paths

`source:` and the `![[…]]` embed use the **filename alone** whenever it's unique vault-wide
(476 of 488 were), falling back to the full relative path when it isn't. `referenced_in` uses
the bare note name on the same rule.

Two reasons:

1. **Move-safety.** Obsidian resolves bare wikilinks by name, so moving an image or a note breaks nothing. Paths would break on every reorganisation.
2. **Search noise.** Repeating the full path four times per sidecar meant any term appearing in a folder name matched every sidecar underneath it. For one test term this inflated results from 70 genuine matches to 230. Shortening the references cut it back to 70.

### Backlinks

Before processing, the driver scans every note for `![[…]]` and `![](…)` embeds and builds an
image → notes map. Each sidecar records which notes embed it, both as a queryable frontmatter
field and as a clickable link. 460 of 483 sidecars got one.

This closes the loop: land on OCR text from a search, click through to the note where you were
discussing it.

### Idempotency and the manifest

State lives at **`<vault>/_OCR/.ocr-manifest.json`** — deliberately *inside the vault*, so each
vault carries its own state and a sandbox copy can't be mistaken for production. (It originally
lived beside the scripts, which meant pointing the tool at a second vault made it think
everything was already done.)

An image is skipped when its path, size, mtime and schema version all match. Bumping `schema`
in the source forces a full rebuild — that's how format changes are rolled out.

### The reaper

Runs **before** the work, on every invocation, so it fires even when there's nothing to OCR:

- deletes sidecars whose source image no longer exists
- prunes manifest entries for missing images
- removes emptied directories in `_OCR/`

Without it, moving an image left the old sidecar behind as an orphan while a new one appeared
at the destination — verified, then fixed.

### Thresholds

Images yielding under 20 characters get no sidecar; the manifest records `status: no-text` so
they're known-examined rather than missed. 5 of 488 fell into this bucket.

---

## `scripts/tidy_attachments.py`

**Rule: an image belongs in the `Attachments` folder of the note that embeds it.**

That matches Obsidian's `attachmentFolderPath: ./Attachments` setting, so future pastes land
where the tidy would put them — the layout stays stable instead of drifting again.

- **Dry-run by default.** `--apply` is required to move anything.
- `--orphans` sweeps unreferenced images into `_Unfiled/`.
- Images embedded from notes in **two different folders** are left alone as ambiguous.
- Emptied directories are removed afterwards.

Safe because every embed in the vault uses bare filenames, so moves can't break links — and
because a pre-flight check confirmed **zero duplicate filenames** across all 488 images, so
nothing can overwrite anything.

---

## `scripts/write_summary.py` + `corpus.sh` — the summary layer

`corpus.sh <folder>` dumps a folder's notes and OCR text for reading. `write_summary.py
<folder> <body.md>` stamps frontmatter — source counts and a **sources digest** (SHA-256 over
sorted filename:size pairs) — and files the result at `_Summaries/<folder>.md`.

### Why this layer is not automated

OCR is a deterministic function: same pixels in, same text out, offline, free. A summary is
judgement — it needs a model, costs tokens, and means sending content somewhere.

The digest exists so the *detection* can be automated even though the writing can't:
`build_ocr.py` already walks every folder and could recompute each digest and stamp
`stale: true` on drifted summaries. The vault would then tell you what's worth rewriting,
without pretending the rewriting is free. Not built yet — see the runbook.
