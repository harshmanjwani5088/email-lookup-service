from pydantic import BaseModel
from app.config import (
    DEFAULT_EMAIL_LIMIT, DEFAULT_HF_LISTING_PAGES, DEFAULT_MODELS_PAGES_PER_USER
)

class ScrapeParams(BaseModel):
    email_limit: int = DEFAULT_EMAIL_LIMIT
    hf_listing_pages: int = DEFAULT_HF_LISTING_PAGES
    models_pages_per_user: int = DEFAULT_MODELS_PAGES_PER_USER

class ScrapeRequest(ScrapeParams):
    pass
