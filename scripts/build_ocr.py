#!/usr/bin/env python3
"""Walk a vault, OCR every image, write _OCR/<path>.ocr.md sidecars. Idempotent via manifest."""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import summary_digest, split_frontmatter, set_fm_field, drop_fm_field
from datetime import date
from pathlib import Path
from urllib.parse import unquote

REPO     = Path(__file__).resolve().parent.parent
_args    = [a for a in sys.argv[1:] if not a.startswith("--")]
_arg     = _args[0] if _args else os.environ.get("OBSIDIAN_VAULT", "")
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
QUIET    = "--quiet" in sys.argv
def say(msg):
    if not QUIET:
        print(msg)
def report(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S ") if QUIET else ""
    print(stamp + msg.strip(), flush=True)

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

def mark_stale_summaries(vault):
    """Recompute each summary's source digest; stamp stale:true/false in place.
    Detection only — regenerating a summary is a judgement call, not a script."""
    root = vault / "_Summaries"
    if not root.is_dir():
        return
    stale = fresh = changed = 0
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(errors="replace")
        fm_text, body = split_frontmatter(text)
        if not fm_text:
            continue
        fm = fm_text.split("\n")
        folder = next((l.split(":", 1)[1].strip().strip('"')
                       for l in fm if l.startswith("source_folder:")), None)
        recorded = next((l.split(":", 1)[1].strip()
                         for l in fm if l.startswith("sources_digest:")), None)
        if folder is None or recorded is None:
            continue
        digest, n_notes, n_shots = summary_digest(str(vault), folder)
        was = next((l.split(":", 1)[1].strip()
                    for l in fm if l.startswith("source_shots:")), "0")
        if digest == recorded:
            fm = set_fm_field(fm, "stale", "false")
            fm = drop_fm_field(fm, "new_since_summary")
            fresh += 1
        else:
            fm = set_fm_field(fm, "stale", "true")
            try:
                delta = n_shots - int(was)
            except ValueError:
                delta = 0
            if delta:
                fm = set_fm_field(fm, "new_since_summary", delta)
            else:
                fm = drop_fm_field(fm, "new_since_summary")
            stale += 1
        rebuilt = "---\n" + "\n".join(fm) + "\n---\n" + body
        if rebuilt != text:
            tmp = path.with_suffix(".md.tmp")
            tmp.write_text(rebuilt); os.replace(tmp, path)
            changed += 1
    # Only speak when a flag actually flipped — otherwise a single stale summary
    # would log on every poll until someone rewrote it.
    if changed:
        report(f"summaries: {changed} changed ({stale} stale, {fresh} current)")


try:
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    os.listdir(VAULT)
except PermissionError:
    sys.exit(f"cannot read {VAULT}\n"
             f"Grant Full Disk Access to this interpreter:\n"
             f"  {os.path.realpath(sys.executable)}\n"
             f"and to {REPO / 'bin' / 'ocrshot'}")

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
if reaped: report(f"reaped {reaped} orphaned sidecars")

say(f"  images found : {len(images)}")
say(f"  linked from  : {len(backlinks)} distinct images referenced by notes")
say(f"  up to date   : {len(images) - len(todo)}")
say(f"  to process   : {len(todo)}")
if not todo:
    MANIFEST.write_text(json.dumps(man, indent=1, sort_keys=True))
    mark_stale_summaries(VAULT)
    sys.exit(0)

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
    say(f"  … {min(i+BATCH,len(todo))}/{len(todo)}  ({time.time()-t0:.0f}s)")

MANIFEST.write_text(json.dumps(man, indent=1, sort_keys=True))
report(f"OCR: {written} written, {skipped} no-text, {failed} failed")
mark_stale_summaries(VAULT)
say(f"  elapsed : {time.time()-t0:.1f}s")
