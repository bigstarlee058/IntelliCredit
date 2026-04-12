"""
NLP Engine - Pillar 2
======================
Sentiment analysis, risk signal extraction, and entity recognition
for credit intelligence from unstructured text.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  SENTIMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════

# Indian credit-context sentiment lexicon
POSITIVE_KEYWORDS = [
    "growth", "profit", "expansion", "revenue increase", "strong performance",
    "upgrade", "stable outlook", "rating upgrade", "new orders", "capacity expansion",
    "debt repayment", "improved margins", "healthy", "robust", "diversified",
    "leader", "market share", "award", "innovation", "strong demand",
    "credit rating affirmed", "consistent", "well-capitalized", "low leverage",
]

NEGATIVE_KEYWORDS = [
    "default", "fraud", "investigation", "loss", "decline", "downgrade",
    "bankruptcy", "npa", "non-performing", "delayed payment", "stress",
    "litigation", "court case", "penalty", "fine", "regulatory action",
    "wilful defaulter", "loan recall", "insolvency", "nclt", "forensic audit",
    "promoter pledge", "stake sale", "debt restructuring", "cdr", "resolution plan",
    "circular trading", "money laundering", "diversion of funds", "related party",
    "qualified opinion", "adverse remark", "going concern", "cash crunch",
]

CRITICAL_KEYWORDS = [
    "fraud", "wilful defaulter", "money laundering", "diversion of funds",
    "ponzi", "scam", "arrested", "absconding", "lookout notice",
    "ed investigation", "cbi", "sfio", "serious fraud",
]

# Minimum critical keyword hits to call the overall sentiment CRITICAL
SENTIMENT_CRITICAL_THRESHOLD = 10


def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text in Indian credit context."""
    if not text:
        return {"score": 0, "label": "NEUTRAL", "confidence": 0}

    text_lower = text.lower()

    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    crit_count = sum(1 for kw in CRITICAL_KEYWORDS if kw in text_lower)

    # Critical flags dominate - but only when a meaningful number are found
    if crit_count >= SENTIMENT_CRITICAL_THRESHOLD:
        score = -0.8 - (crit_count * 0.05)
        score = max(score, -1.0)
        return {
            "score": round(score, 3),
            "label": "CRITICAL",
            "confidence": 0.9,
            "positive_signals": pos_count,
            "negative_signals": neg_count,
            "critical_signals": crit_count,
            "critical_keywords_found": [kw for kw in CRITICAL_KEYWORDS if kw in text_lower],
        }

    # Single fraud keyword: treat as high-negative but not CRITICAL
    if crit_count > 0:
        neg_count += crit_count  # Count toward negative signal
        score = -0.7
        return {
            "score": round(score, 3),
            "label": "NEGATIVE",
            "confidence": 0.8,
            "positive_signals": pos_count,
            "negative_signals": neg_count,
            "critical_signals": crit_count,
            "critical_keywords_found": [kw for kw in CRITICAL_KEYWORDS if kw in text_lower],
        }

    total = pos_count + neg_count
    if total == 0:
        return {"score": 0, "label": "NEUTRAL", "confidence": 0.3,
                "positive_signals": 0, "negative_signals": 0, "critical_signals": 0}

    score = (pos_count - neg_count) / total
    confidence = min(total / 10, 1.0)

    if score > 0.3:
        label = "POSITIVE"
    elif score < -0.3:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"

    return {
        "score": round(score, 3),
        "label": label,
        "confidence": round(confidence, 3),
        "positive_signals": pos_count,
        "negative_signals": neg_count,
        "critical_signals": 0,
    }


def batch_sentiment(articles: list) -> dict:
    """Analyze sentiment across multiple articles."""
    if not articles:
        return {
            "overall_score": None,
            "overall_label": "Not Available",
            "article_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "article_sentiments": []
        }

    sentiments = []
    for article in articles:
        text = article.get("content", "") or article.get("snippet", "")
        s = analyze_sentiment(text)
        s["source"] = article.get("source", "")
        s["title"] = article.get("title", "")
        sentiments.append(s)

    scores = [s["score"] for s in sentiments]
    avg_score = sum(scores) / len(scores) if scores else 0

    has_critical = any(s["label"] == "CRITICAL" for s in sentiments)
    critical_article_count = sum(1 for s in sentiments if s["label"] == "CRITICAL")

    # Only flip to CRITICAL when 3 or more articles are independently CRITICAL
    if has_critical and critical_article_count >= 3:
        overall_label = "CRITICAL"
    elif avg_score > 0.2:
        overall_label = "POSITIVE"
    elif avg_score < -0.2:
        overall_label = "NEGATIVE"
    else:
        overall_label = "NEUTRAL"

    return {
        "overall_score": round(avg_score, 3),
        "overall_label": overall_label,
        "article_count": len(sentiments),
        "positive_count": sum(1 for s in sentiments if s["label"] == "POSITIVE"),
        "negative_count": sum(1 for s in sentiments if s["label"] in ("NEGATIVE", "CRITICAL")),
        "neutral_count": sum(1 for s in sentiments if s["label"] == "NEUTRAL"),
        "article_sentiments": sentiments,
    }


# ═══════════════════════════════════════════════════════════════════
#  RISK SIGNAL EXTRACTION
# ═══════════════════════════════════════════════════════════════════

RISK_PATTERNS = {
    "financial_stress": {
        "keywords": ["cash crunch", "delayed payment", "debt restructuring",
                      "working capital stress", "liquidity crisis", "fund diversion"],
        "severity": "HIGH",
        "category": "Financial Risk",
    },
    "governance_issues": {
        "keywords": ["auditor resignation", "qualified opinion", "related party",
                      "promoter pledge", "insider trading", "board dispute",
                      "cfo resignation", "key managerial"],
        "severity": "HIGH",
        "category": "Governance Risk",
    },
    "legal_risk": {
        "keywords": ["nclt", "insolvency", "court order", "contempt", "injunction",
                      "arbitration award", "winding up", "recovery suit"],
        "severity": "MODERATE",
        "category": "Legal Risk",
    },
    "regulatory_risk": {
        "keywords": ["rbi penalty", "sebi order", "show cause notice", "suspension",
                      "debarment", "license revoked", "non-compliance"],
        "severity": "MODERATE",
        "category": "Regulatory Risk",
    },
    "fraud_indicators": {
        "keywords": ["fraud", "scam", "forgery", "fake invoice", "benami",
                      "shell company", "round tripping", "bogus", "fictitious"],
        "severity": "HIGH",   # Default HIGH; upgraded to CRITICAL only at threshold
        "category": "Fraud Risk",
    },
    "operational_risk": {
        "keywords": ["factory shutdown", "strike", "labour unrest", "supply chain",
                      "raw material shortage", "accident", "environmental violation"],
        "severity": "MODERATE",
        "category": "Operational Risk",
    },
}

# Minimum total fraud keyword hits before the fraud signal is escalated to CRITICAL
FRAUD_CRITICAL_THRESHOLD = 10


def extract_risk_signals(text: str) -> dict:
    """Extract risk signals from text using predefined patterns."""
    if not text:
        return {"signals": [], "risk_level": "Not Assessed", "risk_score": None, "signal_count": 0}

    text_lower = text.lower()
    signals = []
    risk_score = 0

    severity_weights = {"CRITICAL": 30, "HIGH": 15, "MODERATE": 8, "LOW": 3}

    for risk_type, config in RISK_PATTERNS.items():
        found = [kw for kw in config["keywords"] if kw in text_lower]
        if found:
            # For fraud indicators: severity depends on total hit count vs threshold
            if risk_type == "fraud_indicators":
                fraud_total_hits = sum(text_lower.count(kw) for kw in found)
                effective_severity = "CRITICAL" if fraud_total_hits >= FRAUD_CRITICAL_THRESHOLD else "HIGH"
            else:
                effective_severity = config["severity"]
                fraud_total_hits = 0

            weight = severity_weights.get(effective_severity, 5)
            risk_score += len(found) * weight
            signals.append({
                "type": risk_type,
                "category": config["category"],
                "severity": effective_severity,
                "keywords_found": found,
                "count": len(found),
                **({
                    "fraud_keyword_hits": fraud_total_hits,
                    "fraud_threshold": FRAUD_CRITICAL_THRESHOLD,
                } if risk_type == "fraud_indicators" else {}),
            })

    signal_count = len(signals)

    # Determine overall risk level based on signal count and severity
    if signal_count == 0:
        risk_level = "Not Assessed"
    elif signal_count <= 2:
        risk_level = "LOW"
    elif signal_count <= 5:
        risk_level = "MODERATE"
    else:
        risk_level = "HIGH"

    # Only override to CRITICAL if fraud threshold is actually breached
    fraud_sig = next((s for s in signals if s["type"] == "fraud_indicators"), None)
    fraud_hits = fraud_sig["fraud_keyword_hits"] if fraud_sig else 0
    if fraud_sig and fraud_hits >= FRAUD_CRITICAL_THRESHOLD:
        risk_level = "CRITICAL"

    return {
        "signals": sorted(signals, key=lambda s: severity_weights.get(s["severity"], 0), reverse=True),
        "risk_level": risk_level,
        "risk_score": min(risk_score, 100) if signal_count > 0 else None,
        "signal_count": signal_count,
        "fraud_keyword_count": fraud_hits,
        "fraud_threshold": FRAUD_CRITICAL_THRESHOLD,
    }


# ═══════════════════════════════════════════════════════════════════
#  ENTITY EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def extract_entities(text: str) -> dict:
    """Extract financial entities from text using regex patterns."""
    entities = {
        "amounts": [],
        "dates": [],
        "companies": [],
        "percentages": [],
        "ratings": [],
    }

    if not text:
        return entities

    # Amounts (INR)
    amt_pattern = r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh|L|million|mn)?'
    for match in re.finditer(amt_pattern, text, re.IGNORECASE):
        entities["amounts"].append(match.group(0).strip())

    # Dates
    date_patterns = [
        r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
        r'FY\s*\d{2,4}(?:-\d{2,4})?',
        r'Q[1-4]\s*FY\s*\d{2,4}',
    ]
    for pattern in date_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities["dates"].append(match.group(0).strip())

    # Percentages
    pct_pattern = r'(\d+(?:\.\d+)?)\s*%'
    for match in re.finditer(pct_pattern, text):
        entities["percentages"].append(match.group(0).strip())

    # Credit Ratings
    rating_pattern = r'(?:CRISIL|ICRA|CARE|India Ratings|Brickwork|Acuite)\s+[A-D]{1,3}[+-]?'
    for match in re.finditer(rating_pattern, text, re.IGNORECASE):
        entities["ratings"].append(match.group(0).strip())

    # Deduplicate
    for key in entities:
        entities[key] = list(dict.fromkeys(entities[key]))[:20]

    return entities


# ═══════════════════════════════════════════════════════════════════
#  COMBINED NLP PIPELINE
# ═══════════════════════════════════════════════════════════════════

def run_nlp_pipeline(text: str) -> dict:
    """Run complete NLP analysis on text."""
    return {
        "sentiment": analyze_sentiment(text),
        "risk_signals": extract_risk_signals(text),
        "entities": extract_entities(text),
        "text_length": len(text),
    }


def analyze_research_findings(findings: dict) -> dict:
    """Analyze all research findings through NLP pipeline."""
    news_sentiment = batch_sentiment(findings.get("news", []))

    # Combine all text for risk signal extraction
    all_text = []
    for category in ["news", "legal", "sector", "regulatory"]:
        for item in findings.get(category, []):
            text = item.get("content", "") or item.get("snippet", "")
            all_text.append(text)

    combined_text = " ".join(all_text)
    risk_signals = extract_risk_signals(combined_text)
    entities = extract_entities(combined_text)

    return {
        "news_sentiment": news_sentiment,
        "risk_signals": risk_signals,
        "entities": entities,
        "combined_text_length": len(combined_text),
    }
