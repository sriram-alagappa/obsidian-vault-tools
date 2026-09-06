# Runbook

Operational procedures. Read this first on a new machine.

---

## Setting up on a new machine

### 1. Prerequisites

```bash
xcode-select -p          # must print an Xcode or CommandLineTools path
swiftc --version         # Swift 5+
python3 --version        # 3.9+
```

If `xcode-select` fails, install Xcode or run `xcode-select --install`.

### 2. Build

```bash
git clone <this repo> ~/DocumentLocal/obsidian-vault-tools
cd ~/DocumentLocal/obsidian-vault-tools
./build.sh
```

Produces `bin/ocrshot`, a ~120 KB self-contained binary. Nothing else to install — no
Homebrew, no pip, no npm.

### 3. Point at the vault

```bash
export OBSIDIAN_VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault"
```

Add that to `~/.zshrc` to make it permanent.

> ⚠️ **The vault is the folder whose direct children are your notes** — `3D/`, `Engineering/`,
> `Machines/`, `Welcome.md`. It is *not* the `Documents` folder above it, and not the `Obsidian`
> container above that. See [the vault-path trap](#the-vault-path-trap).

### 4. Grant Full Disk Access (only if the vault is in iCloud)

macOS blocks non-Finder processes from `~/Library/Mobile Documents/`. Symptoms: `ls` and `cat`
return **"Operation not permitted"**, while `stat` and `test -e` still work. VS Code shows the
folder as empty rather than erroring.

**System Settings → Privacy & Security → Full Disk Access → +**

Add either:
- **Terminal** — broad, but simple; revoke afterwards if you prefer
- **`bin/ocrshot` alone** — narrow, but the Python driver also needs access, so this only helps for a launchd agent

Quit and reopen the app afterwards; the grant doesn't apply to a running process.

### 5. First run

```bash
python3 scripts/build_ocr.py
```

Expect roughly: `images found: N`, `written: N-few`, `no-text: few`, `failed: 0`, ~70 s for 500
images. Re-running immediately should report `to process: 0`.

### 6. Install the watcher (optional but recommended)

```bash
./scripts/install-agent.sh
```

A launchd agent then runs `build_ocr.py --quiet` every 30 seconds. An uneventful pass costs
~0.2 s and prints nothing, so `~/Library/Logs/obsidian-ocr.log` only ever records real work:

```
2026-09-06 16:55:45 OCR: 1 written, 0 no-text, 0 failed
2026-09-06 16:55:45 summaries: 1 changed (1 stale, 36 current)
```

**launchd inherits no Full Disk Access.** The installer pre-flights this and refuses rather than
installing a silently dead agent. If the vault is in iCloud, grant access to **`/usr/bin/python3`**
*and* **`bin/ocrshot`** (Cmd-Shift-G in the file picker to type a path).

```bash
INTERVAL=120 ./scripts/install-agent.sh     # slower poll
./scripts/install-agent.sh --uninstall      # remove
launchctl print gui/$UID/com.user.obsidian-ocr | head -20
```

---

## Day-to-day

### Refresh OCR after adding screenshots

```bash
python3 scripts/build_ocr.py
```

Idempotent. Processes only new or changed images, reaps sidecars whose image was deleted,
prunes the manifest, removes emptied directories.

### Tidy attachments after reorganising

```bash
python3 scripts/tidy_attachments.py                       # dry run — prints every move
python3 scripts/tidy_attachments.py --apply --orphans     # move them; sweep unreferenced to _Unfiled/
python3 scripts/build_ocr.py                              # reconcile sidecars to new paths
```

**Order matters** — tidy first, then OCR. Reversed, you generate sidecars and immediately reap
and regenerate them.

### Refresh a folder summary

Summaries are written by hand (or with an LLM); only **staleness detection** is automated. Every
pass recomputes each summary's source digest and stamps its frontmatter:

```yaml
stale: true
new_since_summary: 2      # screenshots added since the summary was written
```

Find what needs attention:

```bash
grep -rl '^stale: true' "$OBSIDIAN_VAULT/_Summaries"
```

Better, in Obsidian: a **Bases** view over `tags: [summary]` showing `source_folder`, `stale`,
`new_since_summary` and `generated`, sorted with stale first. That turns "which summaries have
drifted?" into a glance.

To rewrite one:

```bash
scripts/corpus.sh "Research" > /tmp/corpus.txt     # dump notes + OCR text
# read it, write the summary body to /tmp/body.md, then:
python3 scripts/write_summary.py "Research" /tmp/body.md
```

---

## Searching the three layers

Obsidian core search supports path operators. Omnisearch (fuzzy) does not.

| Query | Returns |
|---|---|
| `keyword` | everything — notes, OCR sidecars, summary |
| `keyword -path:"_OCR"` | **notes + summary only — the everyday query** |
| `keyword path:"_Summaries"` | just the digest |
| `keyword path:"_OCR"` | screenshot text only |
| `keyword tag:#ocr` | same, via the tag |

Result *counts* overstate things — `path:` is itself a search term, so it adds one hit per file.
Trust the file list, not the number.

> Do **not** add `_OCR` to Settings → Files and links → **Excluded files**. It suppresses the
> sidecars from results entirely, which defeats the purpose. This was tried and reverted.

---

## Gotchas

### The vault-path trap

Obsidian creates a vault in *whatever folder you point it at* — no confirmation, no sanity
check. Pointing one level too high silently creates a second, empty configuration.

This happened three times in one session: the live vault, the iCloud container, and the
extracted sandbox copy.

**The two-second check after opening any vault:**
1. The vault name at bottom-left is your vault's name — not `Documents`, not the container
2. The file explorer shows your actual folders at the root — not one folder you have to expand

Backup archives are the usual cause: they extract with a wrapper directory. Strip it before
opening.

### iCloud downloads blocked by network security software

If `brctl download` or Finder's "Download Now" fails with *"Your device couldn't connect to the
server"* while ordinary web browsing works, suspect **TLS-inspecting security software**
(corporate TLS-inspection proxies). It breaks iCloud's certificate-pinned content endpoints while
leaving normal HTTPS intact.

Diagnostic: plain `https://www.icloud.com` returns 200, but content transfer stalls.

This is not something to work around. Raise it with IT — the clean evidence is that downloads
succeed the moment inspection is off.

**Images that aren't downloaded cannot be OCR'd.** The pipeline skips them and retries next run.

### Directory listing vs metadata under TCC

Under macOS privacy protection, `stat` and `test -e` succeed while `ls` and `cat` fail. So you
can confirm a known path exists but cannot discover what's in a folder. Useful for scripted
checks; useless for exploration.

### Don't pipe the scripts through `head`

`build_ocr.py` prints progress as it goes. `| head` closes the pipe mid-run and kills it with a
`BrokenPipeError` — leaving the manifest unwritten and the run half-finished. Redirect to a file
instead.

---

## Not yet done

Ranked by value:

1. **Build the Bases view** — the `stale` and `new_since_summary` fields are populated; nothing consumes them yet.
2. **Move the vault out of iCloud** — would eliminate the Full Disk Access requirement, the placeholder problem and the security-software problem in one move. Cost: iOS Obsidian only syncs via iCloud or paid Obsidian Sync, so this means paying for Sync.
3. **Fix any broken embeds the tidy surfaces** — a note referencing a filename that never existed will leave the real image classified as an orphan in `_Unfiled/`. Correct the embed, then move the file back.
4. **Triage `_Unfiled/`** — 23 unreferenced screenshots; see the `_Summaries/_Unfiled.md` note for what they are.
