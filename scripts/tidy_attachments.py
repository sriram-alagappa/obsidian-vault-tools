#!/usr/bin/env python3
"""Move each image next to the note that embeds it: <note folder>/Attachments/.
Dry-run by default; pass --apply to actually move. --orphans moves unreferenced images to _Unfiled/."""
import os, re, sys, glob, shutil, collections
from urllib.parse import unquote
from pathlib import Path

_arg  = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.environ.get("OBSIDIAN_VAULT", "")
if not _arg.strip():
    sys.exit("usage: tidy_attachments.py <vault-path> [--apply] [--orphans]   (or set OBSIDIAN_VAULT)")
VAULT = Path(os.path.expanduser(_arg))
if not VAULT.is_dir():
    sys.exit(f"not a directory: {VAULT}")
if not (VAULT / ".obsidian").is_dir():
    sys.exit(f"{VAULT} has no .obsidian/ — point at the vault itself, "
             "not the folder above it (see docs/RUNBOOK.md)")
APPLY   = "--apply"   in sys.argv
ORPHANS = "--orphans" in sys.argv
EXT   = {".png", ".jpg", ".jpeg"}
embed = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]|!\[[^\]]*\]\(([^)]+)\)")

refs = collections.defaultdict(set)
for f in VAULT.rglob("*.md"):
    if "_OCR" in f.parts or ".obsidian" in f.parts: continue
    folder = str(f.parent.relative_to(VAULT))
    for m in embed.finditer(f.read_text(errors="replace")):
        t = unquote((m.group(1) or m.group(2) or "").strip())
        if os.path.splitext(t)[1].lower() in EXT:
            refs[os.path.basename(t)].add(folder)

moves, orphans, ambiguous, ok = [], [], [], 0
for p in sorted(VAULT.rglob("*")):
    if p.suffix.lower() not in EXT or not p.is_file() or "_OCR" in p.parts: continue
    cur = str(p.parent.relative_to(VAULT))
    homes = refs.get(p.name, set())
    if not homes:            orphans.append(p);   continue
    if len(homes) > 1:       ambiguous.append((p, homes)); continue
    home = next(iter(homes))
    want = "Attachments" if home == "." else f"{home}/Attachments"
    if cur == want: ok += 1
    else: moves.append((p, VAULT / want / p.name, cur, want))

print(f"  in place: {ok}   to move: {len(moves)}   ambiguous: {len(ambiguous)}   orphans: {len(orphans)}\n")
for src, dst, cur, want in moves:
    print(f"    {cur}/{src.name}\n      -> {want}/")
if ambiguous:
    print("\n  ambiguous (left alone):")
    for p, h in ambiguous: print(f"    {p.name}  embedded from: {', '.join(sorted(h))}")

if APPLY:
    done = 0
    for src, dst, _, _ in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists(): print(f"  SKIP (exists): {dst}"); continue
        shutil.move(str(src), str(dst)); done += 1
    if ORPHANS:
        for p in orphans:
            d = VAULT / "_Unfiled"; d.mkdir(exist_ok=True)
            shutil.move(str(p), str(d / p.name)); done += 1
    for d in sorted((d for d in VAULT.rglob("*") if d.is_dir() and "_OCR" not in d.parts),
                    key=lambda x: -len(x.parts)):
        try: d.rmdir(); print(f"  removed empty: {d.relative_to(VAULT)}")
        except OSError: pass
    print(f"\n  moved {done} files")
else:
    print("\n  DRY RUN — nothing moved. Re-run with --apply")
