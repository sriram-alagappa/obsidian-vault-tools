#!/usr/bin/env python3
"""write_summary.py <folder> <body-file> — stamps frontmatter + digest, writes _Summaries/<folder>.md"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import summary_digest
_env = os.environ.get("OBSIDIAN_VAULT", "")
if not _env.strip():
    sys.exit("set OBSIDIAN_VAULT to the vault path")
A = os.path.expanduser(_env)
if not os.path.isdir(A):
    sys.exit(f"not a directory: {A}")
folder, body = sys.argv[1], sys.argv[2]
dig, n_notes, n_shots = summary_digest(A, folder)
fm = ("---\ngenerated: 2026-09-06\n"
      f'source_folder: "{folder}"\nsource_notes: {len(notes)}\nsource_shots: {len(shots)}\n'
      f"sources_digest: {dig}\nstale: false\ntags: [summary]\n---\n\n")
out = f"{A}/_Summaries/{folder}.md"
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(fm + open(body).read())
print(f"  ✓ _Summaries/{folder}.md  ({os.path.getsize(out)}b, {len(notes)}n + {len(shots)}s)")
