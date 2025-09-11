from prometheus_client import (
    Counter, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
)

# counters
USERS_DISCOVERED = Counter("scrape_users_discovered_total", "HF users discovered")
USERS_VISITED    = Counter("scrape_users_visited_total",    "HF users visited")
EMAILS_FOUND     = Counter("emails_found_total",             "Emails extracted (pre-dedup)", ["source"])
EMAILS_WRITTEN   = Counter("emails_written_total",           "Emails written to JSONL")
EMAILS_DEDUP_SKIPPED = Counter("emails_dedup_skipped_total", "Emails skipped due to dedup")
REQUESTS_TOTAL   = Counter("scrape_requests_total",          "HTTP requests made", ["target", "status"])
REQUEST_ERRORS   = Counter("scrape_request_errors_total",    "HTTP request errors", ["target"])

# timings / histos
REQ_LATENCY      = Histogram("scrape_request_latency_seconds", "HTTP request latency", ["target"])
EMAILS_PER_USER  = Histogram("emails_per_user", "Emails per user (post-dedup)", buckets=(0,1,2,3,5,10,20))
RUN_DURATION     = Summary("run_duration_seconds", "Total run duration (seconds)")
USERS_WITH_HITS  = Counter("scrape_users_with_hits_total", "Users with >=1 email")

def get_metrics_text() -> bytes:
    return generate_latest()
