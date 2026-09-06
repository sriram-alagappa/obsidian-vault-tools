"""Shared helpers. The digest definition lives here so build_ocr.py and
write_summary.py can never drift apart on how staleness is computed."""
import glob, hashlib, os

def summary_sources(vault, folder):
    """Notes directly in <folder>, plus every OCR sidecar beneath _OCR/<folder>."""
    notes = sorted(glob.glob(os.path.join(vault, folder, "*.md")))
    shots = sorted(glob.glob(os.path.join(vault, "_OCR", folder, "**", "*.ocr.md"),
                             recursive=True))
    return notes, shots

def summary_digest(vault, folder):
    """(digest, note_count, shot_count) for a folder's current contents."""
    notes, shots = summary_sources(vault, folder)
    blob = "".join(f"{os.path.basename(p)}:{os.path.getsize(p)}" for p in notes + shots)
    return hashlib.sha256(blob.encode()).hexdigest()[:16], len(notes), len(shots)

def split_frontmatter(text):
    """('yaml lines', 'body') for a note starting with ---. ('', text) otherwise."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[4:end], text[end + 5:]

def set_fm_field(fm_lines, key, value):
    """Set or replace a scalar frontmatter field, preserving order."""
    out, done = [], False
    for line in fm_lines:
        if line.split(":", 1)[0].strip() == key and not line.startswith(" "):
            if not done:
                out.append(f"{key}: {value}"); done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}: {value}")
    return out

def drop_fm_field(fm_lines, key):
    return [l for l in fm_lines
            if not (l.split(":", 1)[0].strip() == key and not l.startswith(" "))]
