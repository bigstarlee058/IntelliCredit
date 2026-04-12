"""
Intelli-Credit Configuration
=============================
Central configuration for API keys, model parameters, and pipeline thresholds.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Flask ──
    SECRET_KEY = os.getenv("SECRET_KEY", "intelli-credit-hackathon-2026")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "outputs")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # ── OpenAI ──
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

    # ── Anthropic (Claude) ──
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # ── Databricks ──
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
    DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
    DATABRICKS_SQL_WAREHOUSE_ID = os.getenv("DATABRICKS_SQL_WAREHOUSE_ID", "")
    DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "intelli_credit")
    DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "credit_data")

    # ── Scoring Thresholds ──
    CREDIT_SCORE_EXCELLENT = 80
    CREDIT_SCORE_GOOD = 60
    CREDIT_SCORE_FAIR = 40
    CREDIT_SCORE_POOR = 20

    # ── Risk Premiums (basis points) ──
    RISK_PREMIUM_MAP = {
        "LOW": 50,
        "MODERATE": 150,
        "HIGH": 300,
        "VERY_HIGH": 500,
    }

    # ── Base Interest Rate ──
    BASE_INTEREST_RATE = 9.5  # percent

    # ── Research Agent ──
    MAX_NEWS_ARTICLES = 20
    NEWS_LOOKBACK_DAYS = 365
    RESEARCH_TIMEOUT = 30  # seconds

    # ── Allowed file extensions ──
    ALLOWED_EXTENSIONS = {
        "pdf", "xlsx", "xls", "csv", "docx", "doc", "txt", "json"
    }

    @classmethod
    def allowed_file(cls, filename):
        return "." in filename and \
               filename.rsplit(".", 1)[1].lower() in cls.ALLOWED_EXTENSIONS

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.OUTPUT_FOLDER, exist_ok=True)
