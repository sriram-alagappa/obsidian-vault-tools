# History — 2026-09-06

What was done, in order, and what was learned. Written so the reasoning survives the session.

---

## Starting state

- One Obsidian vault, `My Vault`, in the Obsidian iCloud container
- 144 notes, 486 screenshots, ~320 MB — but only **~100 KB of actual text**. Most notes were walls of `![[…]]` embeds with almost no prose
- A **duplicate vault** sitting in iCloud Drive root, a month stale
- Both Mac and iPhone opening the **wrong folder** as the vault
- Attachments scattered across 35 folders including a misspelled `Attachements` and four Obsidian-generated `Attachments 1` collision folders

## What was fixed, in order

### 1. Found and removed the duplicate

Two folders named `Obsidian` sat side by side in iCloud Drive — one the app's container
(`iCloud~md~obsidian`, which Finder renames and whose `Documents` level it hides), one an
ordinary folder. Only the container copy was current; the other was a month old and missing four
top-level items. Archived, then deleted.

### 2. Fixed the vault path on both devices

Obsidian was opening the *container* rather than `My Vault` inside it. The consequence
wasn't cosmetic: the two devices were reading **different `.obsidian` folders**, so the Mac had
been running without the three community plugins the whole time. Repointed both.

### 3. Backups

Two verified archives on local disk, outside iCloud. Verified by count (636 files) and by
integrity check, then confirmed byte-identical against the live vault before anything destructive
ran.

### 4. Built the OCR pipeline

Developed and tested entirely against an extracted sandbox copy — no permissions needed, live
vault untouched. Four iterations on line assembly (see ARCHITECTURE), then a full 488-image run.

### 5. Tidied attachments

52 images moved to the note that embeds them, 23 unreferenced swept to `_Unfiled/`, 5 empty
folders removed. Dry-run reviewed first.

### 6. Ran it on the live vault

Same two commands, same results — 75 moves, 483 sidecars, 0 failures, ~71 s. Verified
independently afterwards.

### 7. Wrote 37 folder summaries

One per folder with content, `_Summaries/` mirroring the vault structure. 127 KB of prose
covering material that previously existed only as pixels.

---

## What was learned

### The vault-path trap is the root cause of almost everything

Obsidian silently creates a vault wherever you point it. This caused: the wrong-folder opening
on both devices, a stray `.obsidian` beside the real vault, and — later, in the sandbox — the
same mistake a third time. Backup archives make it worse, because they extract with a wrapper
directory.

The tell is always the same: the file explorer shows one folder you have to expand, instead of
your actual folders.

### Two different access problems, easily confused

- **macOS TCC** blocks `ls` and `cat` under `~/Library/Mobile Documents/` while allowing `stat`. Fixed by Full Disk Access. This is why VS Code showed the vault as empty.
- **TLS-inspecting security software** blocked iCloud *downloads* while ordinary browsing worked. Not fixable by permissions — the files simply weren't on disk to read.

Both present as "can't read the vault." They need completely different fixes.

### Bare filenames beat paths

Chosen initially to reduce search noise; turned out to make the whole vault reorganisation-safe.
Moving images and notes breaks nothing because Obsidian resolves bare wikilinks by name.

### Gutter detection was the wrong model

Two hours of the OCR work went into an approach that never fired once. Dense UI screenshots have
no empty vertical bands. Clustering on **left edges** — where panels actually align — worked
immediately.

### Confidence filtering is blunt

Raising the threshold removed real garbage *and* a legitimate URL. Line-level structural
filtering (too short, no alphanumerics) does the useful work without the collateral damage.

### The excluded-files setting is a trap

Adding `_OCR` to Obsidian's "Excluded files" was meant to down-rank sidecars. It suppressed them
from search entirely — hiding the very thing the pipeline exists to surface. Reverted; path
operators do the job precisely and on demand.

---

## Mistakes made along the way

Recorded because they'd otherwise repeat.

- **Concluded "your notes are not duplicated"** after checking only inside the app container, never looking at iCloud Drive's own root. There *was* a duplicate.
- **Recommended `~/Desktop` for backups** without checking that "Sync Desktop & Documents folders" was on — which would have left the backup inside iCloud.
- **Trusted a backup file without opening it.** The registry backup taken during the restructure was empty; relying on it briefly dropped the live vault's registration. Recovered, but the lesson is to verify a backup has content before acting on it.
- **Piped a long-running script through `head`**, killing it mid-run with a broken pipe and leaving a false "finished" impression.
- **Set an Obsidian config in the wrong vault** — written into the sandbox's inner `.obsidian` while Obsidian had the outer folder open, so it appeared to do nothing until the vault path was fixed, at which point it did too much.

---

## Where things stand

| | |
|---|---|
| Vaults | one, correct on Mac and iPhone |
| Backups | two verified archives, local disk |
| Attachments | filed with their notes; 0 misplaced |
| OCR | 483 sidecars, 557 KB of searchable text |
| Summaries | 37 notes, 127 KB |
| Automation | **none yet** — the pipeline is run by hand |

Open items are listed in [RUNBOOK § Not yet done](RUNBOOK.md#not-yet-done).
