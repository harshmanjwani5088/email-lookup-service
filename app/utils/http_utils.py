import time, requests
from typing import Optional, Dict
from app.metrics import REQ_LATENCY, REQUESTS_TOTAL, REQUEST_ERRORS
from app.config import REQUEST_TIMEOUT

def timed_get(url: str, target: str, headers: Optional[Dict[str, str]] = None):
    t0 = time.perf_counter()
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        REQ_LATENCY.labels(target).observe(time.perf_counter() - t0)
        REQUESTS_TOTAL.labels(target, str(resp.status_code)).inc()
        return resp
    except requests.RequestException:
        REQ_LATENCY.labels(target).observe(time.perf_counter() - t0)
        REQUEST_ERRORS.labels(target).inc()
        return None
