# app/utils/verify_email.py
import re, smtplib, random
try:
    import dns.resolver  # pip install dnspython
    _DNS = True
except Exception:
    dns = None
    _DNS = False

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
ROLE = {"admin","support","info","sales","contact","help","security","hr","billing","hello","team"}
DISPOSABLE = {"mailinator.com","guerrillamail.com","10minutemail.com","tempmail.com","yopmail.com"}
NOREPLY = (re.compile(r".+@users\.noreply\.github\.com$", re.I),
           re.compile(r".+@github\.noreply\.com$", re.I))

def _mx(domain: str, timeout=3.0) -> list[str]:
    if not _DNS: return []
    try:
        ans = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        return [str(r.exchange).rstrip(".") for r in sorted(ans, key=lambda r: r.preference)]
    except Exception:
        return []

def _rcpt(mx: str, email: str, timeout=6.0):
    try:
        with smtplib.SMTP(mx, 25, timeout=timeout) as s:
            s.helo("example.com"); s.mail("validator@example.com")
            code, _ = s.rcpt(email)
            if code in (250, 251): return True
            if 500 <= code < 600:  return False
            return None
    except Exception:
        return None

def verify_email(email: str, require_com=False, do_smtp=False) -> dict:
    e = email.strip().lower()
    if not EMAIL_RE.match(e): return {"status":"invalid","reasons":["bad_syntax"]}
    local, domain = e.split("@",1)
    if require_com and not domain.endswith(".com"):
        return {"status":"invalid","reasons":["not_dot_com"]}
    if any(p.search(e) for p in NOREPLY): return {"status":"invalid","reasons":["noreply_github"]}
    if domain in DISPOSABLE: return {"status":"invalid","reasons":["disposable_domain"]}
    reasons = ["role_account"] if local in ROLE else []

    mxs = _mx(domain)
    if not mxs:
        return {"status":"uncertain","reasons":reasons+["mx_unavailable_or_absent"]}

    if do_smtp:
        ok = _rcpt(mxs[0], e)
        if ok is True:  return {"status":"valid","reasons":reasons+["smtp_accept"]}
        if ok is False: return {"status":"invalid","reasons":reasons+["smtp_reject"]}
        return {"status":"uncertain","reasons":reasons+["smtp_uncertain"]}

    return {"status":"uncertain","reasons":reasons+["mx_only_passed"]}
