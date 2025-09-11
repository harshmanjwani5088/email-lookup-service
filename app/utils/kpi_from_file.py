import json, os, re, html
from collections import Counter, defaultdict
from typing import Dict, Iterable, Tuple

# Minimal “is this a real email?” filter (tune as needed)
_EMAIL_RE = re.compile(r'(?:[A-Z0-9._%+-]{1,64})@(?:[A-Z0-9-]{1,63}\.)+(?:[A-Z]{2,15})', re.I)
_BAD_SUFFIXES = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico')
_BAD_EXACT = {'name@example.com', 'user@domain.com', 'actions@github.com'}
_BAD_TLDS = {'local', 'lan', 'internal'}

def _valid(email: str) -> bool:
    e = email.strip().strip('<>,"\'')
    el = e.lower()
    if any(el.endswith(suf) for suf in _BAD_SUFFIXES):
        return False
    if el in _BAD_EXACT:
        return False
    # drop ...@something.local/lan/internal
    tld = el.rsplit('.', 1)[-1]
    if tld in _BAD_TLDS:
        return False
    return _EMAIL_RE.fullmatch(e) is not None

def _domain(email: str) -> str:
    return email.split('@', 1)[-1].lower()

def stream_jsonl(path: str) -> Iterable[Dict]:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

def kpi_from_emails_jsonl(path: str) -> Dict:
    """
    Build KPI purely from the contents of emails.jsonl.
    No hard-coding. Updates whenever the file changes.
    """
    per_source = defaultdict(int)
    per_user_hits = defaultdict(int)
    domains = Counter()

    written = 0
    for row in stream_jsonl(path):
        email = (row.get('email') or '').strip()
        source = row.get('source') or 'unknown'
        user   = row.get('username') or ''
        if not email:
            continue
        if not _valid(email):
            continue

        written += 1
        per_source[source] += 1
        if user:
            per_user_hits[user] += 1
        domains[_domain(email)] += 1

    users_with_hits = sum(1 for _, c in per_user_hits.items() if c > 0)

    # This endpoint can’t know users_discovered/run_seconds without the live run.
    # Return 0 for those, and keep structure identical to your example.
    out = {
        "run_seconds": 0.0,
        "users_discovered": 0,
        "users_with_hits": users_with_hits,
        "hit_rate_percent": 0.0,  # unknown without discovered count
        "new_emails_written": written,
        "emails_by_source": dict(sorted(per_source.items(), key=lambda kv: kv[0])),
        "unique_domains": len(domains),
        "top_domains": domains.most_common(20),
        "out_path": os.path.abspath(path),
    }
    return out
