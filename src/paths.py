from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "output"
SQL_DIR = PROJECT_ROOT / "sql"

PROFILING_REPORT_PATH = OUTPUT_DIR / "profiling_report.json"
DATA_QUALITY_REPORT_PATH = OUTPUT_DIR / "data_quality_report.json"
WAREHOUSE_PATH = OUTPUT_DIR / "warehouse.db"
ANALYTICS_PATH = OUTPUT_DIR / "analytics.json"
