#!/usr/bin/env python3
"""Walk a vault, OCR every image, write _OCR/<path>.ocr.md sidecars. Idempotent via manifest."""
import json, os, re, subprocess, sys, time
from datetime import date
from pathlib import Path
from urllib.parse import unquote

REPO     = Path(__file__).resolve().parent.parent
_arg     = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OBSIDIAN_VAULT", "")
if not _arg.strip():
    sys.exit("usage: build_ocr.py <vault-path>   (or set OBSIDIAN_VAULT)")
VAULT    = Path(_arg).expanduser()
if not VAULT.is_dir():
    sys.exit(f"not a directory: {VAULT}")
if not (VAULT / ".obsidian").is_dir():
    sys.exit(f"{VAULT} has no .obsidian/ — point at the vault itself, "
             "not the folder above it (see docs/RUNBOOK.md)")
BIN      = REPO / "bin" / "ocrshot"
if not BIN.exists():
    sys.exit(f"missing {BIN} — run ./build.sh first")
OUTROOT  = VAULT / "_OCR"
MANIFEST = OUTROOT / ".ocr-manifest.json"   # per-vault: state travels with the vault
MINCHARS = 20
EXT      = {".png", ".jpg", ".jpeg"}
BATCH    = 60

def is_ocr_note(p):  return "_OCR" in p.parts
def is_config(p):    return ".obsidian" in p.parts

# ---- map each image to the notes that embed it, so sidecars link back ----
embed_re = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]|!\[[^\]]*\]\(([^)]+)\)")
backlinks = {}
for note in VAULT.rglob("*.md"):
    if is_ocr_note(note) or is_config(note): continue
    try:    body = note.read_text(errors="replace")
    except Exception: continue
    rel_note = str(note.relative_to(VAULT))[:-3]
    for m in embed_re.finditer(body):
        target = unquote((m.group(1) or m.group(2) or "").strip())
        base = os.path.basename(target)
        if os.path.splitext(base)[1].lower() in EXT:
            backlinks.setdefault(base, set()).add(rel_note)

notecount = {}
for note in VAULT.rglob("*.md"):
    if is_ocr_note(note) or is_config(note): continue
    notecount[note.stem] = notecount.get(note.stem, 0) + 1

def shortlink(rel_note):
    stem = os.path.basename(rel_note)
    return stem if notecount.get(stem, 0) == 1 else rel_note

man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

images = sorted(p for p in VAULT.rglob("*")
                if p.suffix.lower() in EXT and p.is_file()
                and not is_ocr_note(p) and not is_config(p))

namecount = {}
for p in images: namecount[p.name] = namecount.get(p.name, 0) + 1

todo = []
for p in images:
    rel, st = str(p.relative_to(VAULT)), p.stat()
    prev = man.get(rel)
    if prev and prev.get("size") == st.st_size and prev.get("mtime") == int(st.st_mtime) \
       and prev.get("schema") == 4:
        continue
    todo.append(p)

# ---- reap sidecars and manifest entries whose source image is gone ----
live = {str(p.relative_to(VAULT)) for p in images}
reaped = 0
for side in list(OUTROOT.rglob("*.ocr.md")) if OUTROOT.exists() else []:
    stem = str(side.relative_to(OUTROOT))[:-len(".ocr.md")]
    if not any(stem + e in live for e in (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")):
        side.unlink(); reaped += 1
for k in [k for k in man if k not in live]:
    del man[k]
for d in sorted((d for d in OUTROOT.rglob("*") if d.is_dir()), key=lambda x: -len(x.parts)):
    try: d.rmdir()
    except OSError: pass
if reaped: print(f"  reaped  : {reaped} orphaned sidecars")

print(f"  images found : {len(images)}")
print(f"  linked from  : {len(backlinks)} distinct images referenced by notes")
print(f"  up to date   : {len(images) - len(todo)}")
print(f"  to process   : {len(todo)}")
if not todo: sys.exit(0)

t0, written, skipped, failed, linked = time.time(), 0, 0, 0, 0
for i in range(0, len(todo), BATCH):
    chunk = todo[i:i + BATCH]
    out = subprocess.run([str(BIN)] + [str(c) for c in chunk],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        src = Path(r["path"]); rel = str(src.relative_to(VAULT)); st = src.stat()
        refs = sorted(backlinks.get(src.name, []))
        entry = {"size": st.st_size, "mtime": int(st.st_mtime), "chars": r["chars"],
                 "conf": r["meanConfidence"], "cols": r["columns"], "refs": len(refs),
                 "ocr": date.today().isoformat(), "schema": 4}
        if r.get("error"):
            entry["status"] = "error: " + r["error"]; failed += 1
        elif r["chars"] < MINCHARS:
            entry["status"] = "no-text"; skipped += 1
        else:
            entry["status"] = "ok"
            stem = rel[:-len(src.suffix)]
            dest = OUTROOT / (stem + ".ocr.md")
            dest.parent.mkdir(parents=True, exist_ok=True)
            fm  = ["---", f'source: "{src.name}"',
                   f"image_width: {r['width']}", f"image_height: {r['height']}",
                   f"ocr_confidence: {r['meanConfidence']}", f"ocr_chars: {r['chars']}",
                   f"ocr_columns: {r['columns']}", f"ocr_date: {date.today().isoformat()}",
                   "ocr_engine: apple-vision", "tags: [ocr]"]
            if refs:
                fm.append("referenced_in:")
                fm += [f'  - "[[{shortlink(n)}]]"' for n in refs]
                linked += 1
            fm.append("---")
            link = src.name if namecount.get(src.name, 0) == 1 else rel
            parts = ["\n".join(fm), "", f"![[{link}]]", "", "## Extracted text", "", r["text"], ""]
            tmp = dest.with_suffix(".tmp")
            tmp.write_text("\n".join(parts)); os.replace(tmp, dest)
            written += 1
        man[rel] = entry
    print(f"  … {min(i+BATCH,len(todo))}/{len(todo)}  ({time.time()-t0:.0f}s)", flush=True)

MANIFEST.write_text(json.dumps(man, indent=1, sort_keys=True))
print(f"\n  written : {written}  (with backlinks: {linked})\n  no-text : {skipped}\n  failed  : {failed}")
print(f"  elapsed : {time.time()-t0:.1f}s")
