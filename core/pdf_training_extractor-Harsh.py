"""
PDF Training Feature Extractor
================================
Extracts ML-ready features from annual report PDFs for credit risk model training.
Processes individual PDFs or entire folders, caches results to CSV.
"""

import os
import logging
import pandas as pd
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# Path for caching extracted training data
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "pdf_training_data.csv")
DATA_FOLDER = os.path.join(os.path.dirname(__file__), "..", "Data")

# The 14 features expected by the XGBoost model
FEATURE_NAMES = [
    "revenue_growth", "ebitda_margin", "pat_margin",
    "debt_equity_ratio", "current_ratio", "dscr",
    "interest_coverage", "promoter_holding", "years_in_business",
    "debtors_days", "sentiment_score", "litigation_count",
    "cross_verification_score", "industry_risk_score",
]


def extract_features_from_pdf(filepath: str) -> Optional[dict]:
    """
    Extract the 14 ML features + risk label from a single PDF.

    Pipeline:
      1. Parse PDF text via PDFIngestor
      2. Extract financial metrics via regex (FinancialExtractor)
      3. Extract financial metrics via LLM (ai_analyzer)
      4. Merge both extractions, preferring LLM values when available
      5. Map to the 14-feature vector
      6. Assign a heuristic risk label
    """
    from core.data_ingestor import PDFIngestor, FinancialExtractor

    filename = os.path.basename(filepath)
    logger.info(f"Extracting training features from: {filename}")

    try:
        # Step 1: Parse PDF
        ingestor = PDFIngestor(filepath)
        doc_data = ingestor.extract()
        text = doc_data.get("text", "")

        if not text or len(text.strip()) < 200:
            logger.warning(f"Insufficient text extracted from {filename} ({len(text)} chars)")
            return None

        # Step 2: Regex-based extraction
        regex_metrics = FinancialExtractor.extract_from_text(text)

        # Step 3: LLM-based extraction
        llm_metrics = {}
        try:
            from core.ai_analyzer import extract_financial_metrics
            llm_metrics = extract_financial_metrics(text)
            if llm_metrics.get("error"):
                logger.warning(f"LLM extraction returned error for {filename}: {llm_metrics['error']}")
                llm_metrics = {}
        except Exception as e:
            logger.warning(f"LLM extraction failed for {filename}: {e}")

        # Step 4: Merge metrics (LLM preferred, regex as fallback)
        merged = _merge_metrics(regex_metrics, llm_metrics)

        # Step 5: Map to 14-feature vector
        features = _metrics_to_features(merged, filename)

        # Step 6: Assign heuristic risk label
        features["target"] = _assign_risk_label(features)
        features["source_file"] = filename

        logger.info(f"Successfully extracted features from {filename}: target={features['target']}")
        return features

    except Exception as e:
        logger.error(f"Failed to extract features from {filename}: {e}")
        return None


def _merge_metrics(regex_metrics: dict, llm_metrics: dict) -> dict:
    """Merge regex and LLM metrics, preferring LLM values when non-zero."""
    merged = {}

    # Helper to get a scalar value from potentially nested dicts
    def _get_val(d, key, sub_key="value"):
        val = d.get(key, 0)
        if isinstance(val, dict):
            val = val.get(sub_key, 0) or 0
        if isinstance(val, str):
            import re as _re
            cleaned = _re.sub(r"[^\d.\-]", "", val)
            try:
                val = float(cleaned)
            except (ValueError, TypeError):
                val = 0
        return val or 0

    def _get_sub(d, key, sub_key, default=0):
        val = d.get(key)
        if isinstance(val, dict):
            return val.get(sub_key, default) or default
        return default

    # Revenue
    llm_rev = _get_val(llm_metrics, "revenue")
    regex_rev = _get_val(regex_metrics, "revenue")
    merged["revenue_cr"] = llm_rev if llm_rev else regex_rev

    # Revenue growth
    merged["revenue_growth"] = _get_sub(llm_metrics, "revenue", "growth_pct", 0)

    # EBITDA
    llm_ebitda = _get_val(llm_metrics, "ebitda")
    regex_ebitda = _get_val(regex_metrics, "ebitda")
    merged["ebitda_cr"] = llm_ebitda if llm_ebitda else regex_ebitda

    # EBITDA margin
    merged["ebitda_margin"] = _get_sub(llm_metrics, "ebitda", "margin_pct", 0)
    if not merged["ebitda_margin"] and merged["revenue_cr"]:
        merged["ebitda_margin"] = round(merged["ebitda_cr"] / max(merged["revenue_cr"], 0.01) * 100, 1)

    # PAT
    llm_pat = _get_val(llm_metrics, "pat")
    regex_pat = _get_val(regex_metrics, "pat")
    merged["pat_cr"] = llm_pat if llm_pat else regex_pat

    # PAT margin
    merged["pat_margin"] = _get_sub(llm_metrics, "pat", "margin_pct", 0)
    if not merged["pat_margin"] and merged["revenue_cr"]:
        merged["pat_margin"] = round(merged["pat_cr"] / max(merged["revenue_cr"], 0.01) * 100, 1)

    # Debt & ratios
    merged["total_debt_cr"] = _get_val(llm_metrics, "total_debt") or _get_val(regex_metrics, "total_debt")
    merged["net_worth_cr"] = _get_val(llm_metrics, "net_worth") or _get_val(regex_metrics, "net_worth")

    merged["debt_equity_ratio"] = (
        _get_val(llm_metrics, "debt_equity_ratio")
        or _get_val(regex_metrics, "debt_equity")
        or (round(merged["total_debt_cr"] / max(merged["net_worth_cr"], 0.01), 2)
            if merged["total_debt_cr"] else 0)
    )

    merged["current_ratio"] = (
        _get_val(llm_metrics, "current_ratio")
        or _get_val(regex_metrics, "current_ratio")
        or 1.5  # default
    )

    merged["dscr"] = _get_val(llm_metrics, "dscr") or 1.5
    merged["interest_coverage"] = (
        _get_val(llm_metrics, "interest_coverage_ratio") or 3.0
    )

    # Other fields
    merged["promoter_holding"] = _get_val(llm_metrics, "promoter_holding_pct") or 50
    merged["debtors_days"] = _get_val(llm_metrics, "debtors_days") or 60

    # Company name for logging
    merged["company_name"] = llm_metrics.get("company_name", "Unknown")

    return merged


def _metrics_to_features(merged: dict, filename: str) -> dict:
    """Convert merged metrics into the 14-feature vector."""
    def _to_float(val, default):
        if val in ("N/A", "Not Available", None):
            return float(default)
        try:
            return float(val)
        except (ValueError, TypeError):
            return float(default)

    return {
        "revenue_growth": _to_float(merged.get("revenue_growth", 0), 0),
        "ebitda_margin": _to_float(merged.get("ebitda_margin", 0), 0),
        "pat_margin": _to_float(merged.get("pat_margin", 0), 0),
        "debt_equity_ratio": _to_float(merged.get("debt_equity_ratio", 1.0), 1.0),
        "current_ratio": _to_float(merged.get("current_ratio", 1.5), 1.5),
        "dscr": _to_float(merged.get("dscr", 1.5), 1.5),
        "interest_coverage": _to_float(merged.get("interest_coverage", 3.0), 3.0),
        "promoter_holding": _to_float(merged.get("promoter_holding", 50), 50),
        "years_in_business": 10.0,  # Default; hard to extract reliably from annual reports
        "debtors_days": _to_float(merged.get("debtors_days", 60), 60),
        "sentiment_score": 0.0,  # Neutral default for training data
        "litigation_count": 0.0,  # Default for training data
        "cross_verification_score": 80.0,  # Default for training data
        "industry_risk_score": 5.0,  # Mid-range default
    }


def _assign_risk_label(features: dict) -> int:
    """
    Assign a heuristic risk label based on financial health signals.
    Returns 1 for high risk, 0 for low risk.
    """
    risk_score = 0

    # High leverage
    if features["debt_equity_ratio"] > 3.0:
        risk_score += 3
    elif features["debt_equity_ratio"] > 2.0:
        risk_score += 2
    elif features["debt_equity_ratio"] > 1.5:
        risk_score += 1

    # Negative profitability
    if features["pat_margin"] < -5:
        risk_score += 3
    elif features["pat_margin"] < 0:
        risk_score += 2
    elif features["pat_margin"] < 3:
        risk_score += 1

    # Low DSCR
    if features["dscr"] < 1.0:
        risk_score += 3
    elif features["dscr"] < 1.2:
        risk_score += 2
    elif features["dscr"] < 1.5:
        risk_score += 1

    # Low current ratio
    if features["current_ratio"] < 1.0:
        risk_score += 2
    elif features["current_ratio"] < 1.2:
        risk_score += 1

    # Revenue decline
    if features["revenue_growth"] < -10:
        risk_score += 3
    elif features["revenue_growth"] < 0:
        risk_score += 1

    # High debtor days
    if features["debtors_days"] > 120:
        risk_score += 2
    elif features["debtors_days"] > 90:
        risk_score += 1

    # Low interest coverage
    if features["interest_coverage"] < 1.5:
        risk_score += 2
    elif features["interest_coverage"] < 2.5:
        risk_score += 1

    return 1 if risk_score >= 5 else 0


def process_training_folder(folder: str = None) -> pd.DataFrame:
    """
    Process all PDFs in a folder and return a training DataFrame.
    Results are cached to models/pdf_training_data.csv.
    """
    folder = folder or DATA_FOLDER
    folder = os.path.abspath(folder)

    if not os.path.exists(folder):
        logger.error(f"Training data folder not found: {folder}")
        return pd.DataFrame(columns=FEATURE_NAMES + ["target", "source_file"])

    pdf_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_files:
        logger.warning(f"No PDF files found in {folder}")
        return pd.DataFrame(columns=FEATURE_NAMES + ["target", "source_file"])

    logger.info(f"Processing {len(pdf_files)} PDF files from {folder}")

    rows = []
    for pdf_path in pdf_files:
        features = extract_features_from_pdf(pdf_path)
        if features is not None:
            rows.append(features)

    if not rows:
        logger.warning("No features extracted from any PDFs")
        return pd.DataFrame(columns=FEATURE_NAMES + ["target", "source_file"])

    df = pd.DataFrame(rows)

    # Save cache
    cache_path = os.path.abspath(CACHE_PATH)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df.to_csv(cache_path, index=False)
    logger.info(f"Saved {len(df)} training samples to {cache_path}")

    return df


def extract_and_append(filepath: str) -> pd.DataFrame:
    """
    Extract features from a single PDF and append to the cached training data.
    Returns the updated full DataFrame.
    """
    features = extract_features_from_pdf(filepath)
    if features is None:
        logger.warning(f"Could not extract features from {filepath}")
        return load_cached_data()

    new_row = pd.DataFrame([features])
    cache_path = os.path.abspath(CACHE_PATH)

    if os.path.exists(cache_path):
        existing = pd.read_csv(cache_path)
        # Remove any existing row with the same source file
        existing = existing[existing["source_file"] != features["source_file"]]
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        combined = new_row

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    combined.to_csv(cache_path, index=False)
    logger.info(f"Appended features from {os.path.basename(filepath)}, total rows: {len(combined)}")

    return combined


def load_cached_data() -> pd.DataFrame:
    """Load cached training data if available."""
    cache_path = os.path.abspath(CACHE_PATH)
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)
    return pd.DataFrame(columns=FEATURE_NAMES + ["target", "source_file"])
