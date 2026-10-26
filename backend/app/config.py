import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = ROOT / "dataset" / "skills_taxonomy.csv"
DATA = UPLOADS = REPORTS = DB = None

DEFAULT_SETTINGS = {"max_files": 20, "max_size_mb": 10, "retention_days": 0}
HARD_LIMITS = {"max_files": (1, 50), "max_size_mb": (1, 25), "retention_days": (0, 3650)}
SUPPORTED_EXT = ("pdf", "docx")
MAX_WORKERS = 3          # bounded concurrency for batch processing
MAX_PAGES = 30           # pages parsed per PDF (processing bound)


def set_data_dir(path):
    global DATA, UPLOADS, REPORTS, DB
    DATA = Path(path)
    UPLOADS, REPORTS = DATA / "uploads", DATA / "reports"
    DB = DATA / "resumatch.db"
    for p in (DATA, UPLOADS, REPORTS):
        p.mkdir(parents=True, exist_ok=True)


def cors_origins():
    return [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
