import os, json
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from starlette.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr  

from app.metrics import get_metrics_text, CONTENT_TYPE_LATEST
from app.models.schema import ScrapeRequest, ScrapeParams
from app.services import scraper
from app.utils.io_utils import tail_jsonl
from app.utils.kpi_from_file import kpi_from_emails_jsonl
from app.utils.verify_email import verify_email  
from app.config import OUT_PATH

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "running": scraper.is_running()}

@router.get("/metrics")
def metrics():
    data = get_metrics_text()  # bytes
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)

@router.get("/kpi/latest")
def kpi_latest():
    file_view = kpi_from_emails_jsonl(OUT_PATH)
    run_view = scraper.get_last_kpi() or {}
    for k in ("run_seconds", "users_discovered", "users_with_hits", "hit_rate_percent"):
        if k in run_view:
            file_view[k] = run_view[k]
    if file_view.get("new_emails_written", 0) == 0 and os.path.exists("kpi_latest.json"):
        try:
            with open("kpi_latest.json", "r", encoding="utf-8") as f:
                stored = json.load(f)
            for k, v in stored.items():
                file_view.setdefault(k, v)
        except Exception:
            pass
    return file_view

@router.post("/scrape")
def start_scrape(req: ScrapeRequest, background: BackgroundTasks):
    if scraper.is_running():
        raise HTTPException(status_code=409, detail="Scrape already running")
    def _job():
        try:
            scraper.run_scrape(ScrapeParams(**req.model_dump()))
        except Exception as e:
            print("Scrape error:", e)
    background.add_task(_job)
    return {"status": "started", "params": req.model_dump()}

@router.get("/emails")
def get_emails(limit: int = Query(50, ge=1, le=1000)):
    return tail_jsonl(OUT_PATH, limit)

# ---- NEW: /verify endpoint ----
class VerifyIn(BaseModel):
    email: EmailStr

class VerifyOut(BaseModel):
    email: EmailStr
    status: str
    reasons: list[str]

@router.post("/verify", response_model=VerifyOut)
def verify_email_endpoint(
    body: VerifyIn,
    require_com: bool = Query(False, description="Only allow .com domains"),
    smtp: bool = Query(False, description="Enable SMTP RCPT probe")
):
    res = verify_email(str(body.email), require_com=require_com, do_smtp=smtp)
    return {"email": body.email, **res}

@router.get("/")
def root():
    return {
        "app": "Email Lookup Service (FastAPI)",
        "endpoints": {
            "GET /health": "health check",
            "POST /scrape": "start background scrape",
            "GET /kpi/latest": "dynamic KPI from emails.jsonl (+run overlay)",
            "GET /emails?limit=N": "tail emails.jsonl",
            "POST /verify": "email validity check",
            "GET /metrics": "Prometheus metrics",
        },
        "out_path": os.path.abspath(OUT_PATH),
    }
