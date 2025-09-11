
import os, time, random, threading
from typing import List, Tuple, Dict
from bs4 import BeautifulSoup
import requests

from app.config import HF_BASE, GITHUB_API, GITHUB_TOKEN, UA, OUT_PATH
from app.metrics import (
    USERS_DISCOVERED, USERS_VISITED, EMAILS_FOUND, EMAILS_WRITTEN,
    EMAILS_DEDUP_SKIPPED, EMAILS_PER_USER, USERS_WITH_HITS, RUN_DURATION
)
from app.utils.email_utils import extract_emails
from app.utils.http_utils import timed_get
from app.utils.io_utils import append_jsonl, load_existing_emails
from app.models.schema import ScrapeParams

_lock = threading.Lock()
_last_kpi: Dict[str, object] = {}
_running = False

def scrape_hf_users(pages: int) -> List[str]:
    users: List[str] = []
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    for page in range(1, pages + 1):
        url = f"{HF_BASE}/models?p={page}&sort=downloads"
        resp = timed_get(url, "hf_models_list", headers={"User-Agent": UA})
        if not resp or resp.status_code != 200:
            time.sleep(0.2); continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not href.startswith("/"):
                continue
            if any(bad in href for bad in ["/models", "/datasets", "/spaces", "/docs", "/blog", "/tasks"]):
                continue
            root = href.strip("/").split("/")[0]
            if root and len(root) < 40 and root not in users:
                users.append(root)
        time.sleep(0.1)
    if users:
        USERS_DISCOVERED.inc(len(users))
    random.shuffle(users)
    return users

def scrape_hf_profile(user: str) -> Tuple[list[str], list[str], list[str]]:
    url = f"{HF_BASE}/{user}"
    resp = timed_get(url, "hf_profile", headers={"User-Agent": UA})
    if not resp or resp.status_code != 200:
        return [], [], []
    text = resp.text
    emails = extract_emails(text)
    soup = BeautifulSoup(text, "html.parser")
    gh_links, web_links = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        if "github.com" in href.lower():
            gh_links.append(href.split("?")[0].split("#")[0].rstrip("/"))
        if href.startswith("http") and "huggingface.co" not in href:
            web_links.append(href.split("?")[0].split("#")[0].rstrip("/"))
    # uniq
    gh_links = list(dict.fromkeys(gh_links))
    web_links = list(dict.fromkeys(web_links))
    return emails, gh_links, web_links

def get_user_models(user: str, pages: int) -> list[str]:
    slugs: list[str] = []
    for p in range(1, pages + 1):
        url = f"{HF_BASE}/{user}?p={p}&sort=models"
        resp = timed_get(url, "hf_models_of_user", headers={"User-Agent": UA})
        if not resp or resp.status_code != 200:
            time.sleep(0.1); continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select(f"a[href^='/{user}/']"):
            href = a.get("href", "").split("?")[0].split("#")[0].rstrip("/")
            parts = href.strip("/").split("/")
            if len(parts) == 2 and href not in slugs:  # /user/model
                slugs.append(href)
        time.sleep(0.1)
    return slugs

def scrape_hf_model_page(slug: str) -> Tuple[list[str], list[str]]:
    url = f"{HF_BASE}/{slug.lstrip('/')}"
    resp = timed_get(url, "hf_model_page", headers={"User-Agent": UA})
    if not resp or resp.status_code != 200:
        return [], []
    text = resp.text
    emails = extract_emails(text)
    soup = BeautifulSoup(resp.text, "htmlparser")
    soup = BeautifulSoup(resp.text, "html.parser")  # fix parser typo
    gh_links = [a["href"].split("?")[0].split("#")[0].rstrip("/")
                for a in soup.find_all("a", href=True)
                if "github.com" in a["href"].lower()]
    gh_links = list(dict.fromkeys(gh_links))
    return emails, gh_links

def scrape_website_for_emails(url: str) -> list[str]:
    resp = timed_get(url, "website", headers={"User-Agent": UA})
    if not resp or resp.status_code != 200:
        return []
    return extract_emails(resp.text)

def _gh_headers() -> dict:
    h = {"User-Agent": UA}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def get_github_emails(user_or_url: str) -> list[str]:
    username = user_or_url.rstrip("/").split("/")[-1] if "github.com" in user_or_url else user_or_url
    resp = timed_get(f"{GITHUB_API}/users/{username}/repos", "github_repos", headers=_gh_headers())
    if not resp or resp.status_code != 200:
        return []
    repos_json = resp.json() if isinstance(resp.json(), list) else []
    emails: list[str] = []
    for repo in repos_json[:4]:
        name = repo.get("name")
        if not name:
            continue
        resp2 = timed_get(f"{GITHUB_API}/repos/{username}/{name}/commits?per_page=100",
                          "github_commits", headers=_gh_headers())
        if not resp2 or resp2.status_code != 200:
            time.sleep(0.1); continue
        commits = resp2.json() if isinstance(resp2.json(), list) else []
        for c in commits:
            for path in (("commit", "author", "email"), ("commit", "committer", "email")):
                ref = c
                for k in path:
                    ref = ref.get(k) if isinstance(ref, dict) else None
                    if ref is None:
                        break
                if isinstance(ref, str):
                    emails.append(ref)
        time.sleep(0.1)
    # reuse extraction (filters noreply + dedup)
    return extract_emails("\n".join(emails))

def run_scrape(params: ScrapeParams) -> dict:
    global _running, _last_kpi
    if _running:
        raise RuntimeError("Scrape already running")
    t0 = time.perf_counter()
    _running = True
    try:
        users = scrape_hf_users(params.hf_listing_pages)
        seen_emails = load_existing_emails(OUT_PATH)

        found_this_run = 0
        users_with_hits = 0
        emails_by_source: Dict[str, int] = {
            "huggingface-profile": 0, "huggingface-model": 0, "website": 0, "github": 0
        }
        domains_count: Dict[str, int] = {}

        for user in users:
            if found_this_run >= params.email_limit:
                break
            USERS_VISITED.inc()
            per_user_written = 0

            prof_emails, gh_links_on_prof, web_links = scrape_hf_profile(user)
            for e in prof_emails:
                if e in seen_emails:
                    EMAILS_DEDUP_SKIPPED.inc(); continue
                append_jsonl(OUT_PATH, {"username": user, "email": e, "source": "huggingface-profile"})
                EMAILS_FOUND.labels("huggingface-profile").inc()
                EMAILS_WRITTEN.inc()
                emails_by_source["huggingface-profile"] += 1
                seen_emails.add(e); found_this_run += 1; per_user_written += 1
                dom = e.split("@")[-1].lower(); domains_count[dom] = domains_count.get(dom, 0) + 1
                if found_this_run >= params.email_limit: break
            if found_this_run >= params.email_limit: break

            gh_links_accum = list(gh_links_on_prof)
            for slug in get_user_models(user, params.models_pages_per_user):
                if found_this_run >= params.email_limit: break
                m_emails, m_gh_links = scrape_hf_model_page(slug)
                for e in m_emails:
                    if e in seen_emails:
                        EMAILS_DEDUP_SKIPPED.inc(); continue
                    append_jsonl(OUT_PATH, {"username": user, "email": e, "source": "huggingface-model"})
                    EMAILS_FOUND.labels("huggingface-model").inc()
                    EMAILS_WRITTEN.inc()
                    emails_by_source["huggingface-model"] += 1
                    seen_emails.add(e); found_this_run += 1; per_user_written += 1
                    dom = e.split("@")[-1].lower(); domains_count[dom] = domains_count.get(dom, 0) + 1
                    if found_this_run >= params.email_limit: break
                for g in m_gh_links:
                    if g not in gh_links_accum:
                        gh_links_accum.append(g)

            if found_this_run >= params.email_limit: break

            for link in web_links:
                if found_this_run >= params.email_limit: break
                for e in scrape_website_for_emails(link):
                    if e in seen_emails:
                        EMAILS_DEDUP_SKIPPED.inc(); continue
                    append_jsonl(OUT_PATH, {"username": user, "email": e, "source": "website"})
                    EMAILS_FOUND.labels("website").inc()
                    EMAILS_WRITTEN.inc()
                    emails_by_source["website"] += 1
                    seen_emails.add(e); found_this_run += 1; per_user_written += 1
                    dom = e.split("@")[-1].lower(); domains_count[dom] = domains_count.get(dom, 0) + 1
                    if found_this_run >= params.email_limit: break

            if found_this_run >= params.email_limit: break

            for gh in gh_links_accum:
                if found_this_run >= params.email_limit: break
                for e in get_github_emails(gh):
                    if e in seen_emails:
                        EMAILS_DEDUP_SKIPPED.inc(); continue
                    append_jsonl(OUT_PATH, {"username": user, "email": e, "source": "github"})
                    EMAILS_FOUND.labels("github").inc()
                    EMAILS_WRITTEN.inc()
                    emails_by_source["github"] += 1
                    seen_emails.add(e); found_this_run += 1; per_user_written += 1
                    dom = e.split("@")[-1].lower(); domains_count[dom] = domains_count.get(dom, 0) + 1
                    if found_this_run >= params.email_limit: break

            if per_user_written > 0:
                users_with_hits += 1
                EMAILS_PER_USER.observe(per_user_written)

        run_secs = time.perf_counter() - t0
        RUN_DURATION.observe(run_secs)

        total_users = len(users)
        hit_rate = (users_with_hits / total_users * 100.0) if total_users else 0.0
        kpi_snapshot = {
            "run_seconds": round(run_secs, 2),
            "users_discovered": total_users,
            "users_with_hits": users_with_hits,
            "hit_rate_percent": round(hit_rate, 2),
            "new_emails_written": found_this_run,
            "emails_by_source": emails_by_source,
            "unique_domains": len(domains_count),
            "top_domains": sorted(domains_count.items(), key=lambda x: x[1], reverse=True)[:10],
            "out_path": os.path.abspath(OUT_PATH),
        }
        _last_kpi = kpi_snapshot
        with open("kpi_latest.json", "w", encoding="utf-8") as f:
            import json; json.dump(kpi_snapshot, f, ensure_ascii=False, indent=2)
        return kpi_snapshot
    finally:
        _running = False

def is_running() -> bool:
    return _running

def get_last_kpi() -> Dict[str, object]:
    global _last_kpi
    return _last_kpi
