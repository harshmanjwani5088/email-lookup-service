import os

HF_BASE = os.getenv("HF_BASE", "https://huggingface.co")
GITHUB_API = os.getenv("GITHUB_API", "https://api.github.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # set to avoid rate limits

UA = os.getenv("UA", "email-lookup-service/fastapi/1.0 (+hf_gh)")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
OUT_PATH = os.getenv("OUT_PATH", "emails.jsonl")

DEFAULT_EMAIL_LIMIT = int(os.getenv("EMAIL_LIMIT", "200"))
DEFAULT_HF_LISTING_PAGES = int(os.getenv("HF_LISTING_PAGES", "40"))
DEFAULT_MODELS_PAGES_PER_USER = int(os.getenv("HF_MODELS_PAGES_PER_USER", "3"))
