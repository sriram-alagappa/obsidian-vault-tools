#!/bin/bash
# corpus.sh <folder> — dump one folder's notes + OCR text, for reading or summarising.
# Requires OBSIDIAN_VAULT to be set.
A="${OBSIDIAN_VAULT:?set OBSIDIAN_VAULT to the vault path}"
F="$1"
echo "########## NOTES: $F ##########"
for f in "$A/$F"/*.md; do [ -e "$f" ] || continue; echo "--- NOTE: $(basename "$f")"; cat "$f"; echo; done
echo "########## OCR: $F ##########"
find "$A/_OCR/$F" -maxdepth 2 -name '*.ocr.md' 2>/dev/null | sort | while read -r f; do
  echo "--- $(basename "$f" .ocr.md)"; sed -n '/^## Extracted text/,$p' "$f" | tail -n +3
done
