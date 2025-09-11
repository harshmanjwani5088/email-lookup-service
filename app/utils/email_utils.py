import re, html

# common obfuscations
_OBF_PATTERNS = [
    (r"\s*\[\s*at\s*\]\s*", "@"), (r"\s*\(\s*at\s*\)\s*", "@"), (r"\s+at\s+", "@"),
    (r"\s*\[\s*dot\s*\]\s*", "."), (r"\s*\(\s*dot\s*\)\s*", "."), (r"\s+dot\s+", "."),
    (r"\s*{\s*at\s*}\s*", "@"), (r"\s*{\s*dot\s*}\s*", "."),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

def deobfuscate(text: str) -> str:
    t = html.unescape(text)
    t = re.sub(r"[\(\)\[\]\{\}<>]", " ", t)
    t = re.sub(r"\s*-\s*", "-", t)
    for pat, rep in _OBF_PATTERNS:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t)

def extract_emails(text: str) -> list[str]:
    t = deobfuscate(text)
    out: list[str] = []
    for e in EMAIL_RE.findall(t):
        el = e.lower()
        if "noreply" in el or "users.noreply.github.com" in el:
            continue
        out.append(e)
    # dedup preserve order
    seen, uniq = set(), []
    for e in out:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq
