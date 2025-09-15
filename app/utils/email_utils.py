import re
import html
from typing import List

# --- Common obfuscations (kept from your version) ---
_OBF_PATTERNS = [
    (r"\s*\[\s*at\s*\]\s*", "@"), (r"\s*\(\s*at\s*\)\s*", "@"), (r"\s+at\s+", "@"),
    (r"\s*\[\s*dot\s*\]\s*", "."), (r"\s*\(\s*dot\s*\)\s*", "."), (r"\s+dot\s+", "."),
    (r"\s*{\s*at\s*}\s*", "@"), (r"\s*{\s*dot\s*}\s*", "."),
]

# --- Blocked extensions right after a match (to avoid filenames/asset URLs) ---
_NEXT_IS_BANNED_EXT = re.compile(
    r'^\.(?:jpg|jpeg|png|gif|webp|svg|bmp|tif|tiff|ico|heic|heif|psd)(?:\b|[?#/])',
    re.IGNORECASE
)

# --- Primary email regex: ONLY .com TLD ---
EMAIL_RE = re.compile(
    r"""
    (?ix)
    [A-Z0-9._%+\-]+         # local part
    @
    [A-Z0-9.-]+             # domain labels
    \.com\b                 # ONLY .com
    """,
    re.IGNORECASE | re.VERBOSE,
)

def deobfuscate(text: str) -> str:
    t = html.unescape(text or "")
    t = re.sub(r"[\(\)\[\]\{\}<>]", " ", t)   # break <at> / [dot] tricks
    t = re.sub(r"\s*-\s*", "-", t)            # normalize "name - at - domain"
    for pat, rep in _OBF_PATTERNS:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()

def extract_emails(text: str) -> List[str]:
    """
    Extract only .com emails. Filters out:
      - filename/asset endings like '.jpg' right after the .com
      - noreply and GitHub noreply addresses
      - domains with broken labels (underscores, empty, leading/trailing '-')
    Dedupes while preserving order.
    """
    t = deobfuscate(text)
    if not t:
        return []

    out: list[str] = []
    for m in EMAIL_RE.finditer(t):
        e = m.group(0)
        el = e.lower()

        # Skip noreply variants
        if "noreply" in el or "users.noreply.github.com" in el:
            continue

        # If immediately followed by an image/resource extension, drop it
        tail = t[m.end(): m.end() + 20]
        if _NEXT_IS_BANNED_EXT.search(tail):
            continue

        # Domain sanity (no underscores, no empty/invalid labels)
        _, _, domain = el.rpartition("@")
        if not domain.endswith(".com"):
            continue
        labels = domain.split(".")
        if any(not lbl or "_" in lbl or lbl.startswith("-") or lbl.endswith("-") for lbl in labels):
            continue

        out.append(e)

    # Dedup preserve order
    seen, uniq = set(), []
    for e in out:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq

__all__ = ["deobfuscate", "extract_emails"]
