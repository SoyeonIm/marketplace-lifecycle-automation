from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = PROJECT_ROOT / "reports"
SQL_DIR = PROJECT_ROOT / "sql"
DATABASE_PATH = PROJECT_ROOT / "data" / "warehouse.sqlite"

CAMPAIGN_ID = "seller_reactivation_2026_08"
EXPERIMENT_ID = "exp_seller_reactivation_2026_08"
CAMPAIGN_AT = datetime(2026, 8, 1, 9, 0, 0)
CAMPAIGN_DATE = CAMPAIGN_AT.strftime("%Y-%m-%d %H:%M:%S")
ANALYSIS_END_AT = datetime(2026, 8, 15, 23, 59, 59)
ANALYSIS_END = ANALYSIS_END_AT.strftime("%Y-%m-%d %H:%M:%S")
RECENT_ACTIVITY_START = (CAMPAIGN_AT - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
CONTACT_CAP_START = (CAMPAIGN_AT - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
LAPSED_CUTOFF = (CAMPAIGN_AT - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

CATEGORIES = [
    "Home & living",
    "Computers",
    "Electronics",
    "Fashion",
    "Sports",
    "Motors parts",
    "Collectables",
]
REGIONS = ["Auckland", "Wellington", "Canterbury", "Waikato", "Otago", "Other"]


def ensure_directories() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

