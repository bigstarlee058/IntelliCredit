"""
Scoring Engine - Pillar 3
===========================
Five Cs credit scoring model with ML-based risk prediction
and SHAP explainability.
"""

import json
import logging
import os
import pickle
from typing import Optional

import numpy as np

from config import Config

logger = logging.getLogger(__name__)


class FiveCsScorer:
    """
    Score borrowers on the Five Cs of Credit:
      Character (25%), Capacity (25%), Capital (20%),
      Collateral (15%), Conditions (15%)
    """

    WEIGHTS = {
        "character": 0.25,
        "capacity": 0.25,
        "capital": 0.20,
        "collateral": 0.15,
        "conditions": 0.15,
    }

    def __init__(self):
        self.scores = {}
        self.details = {}
        self.overall_score = 0
        self.ml_score = None
        self.ml_explanation = None

    def score(self, financial_data: dict, research_data: dict,
              nlp_data: dict, cross_verification: dict,
              qualitative_data: dict = None) -> dict:
        """Run complete Five Cs scoring."""

        self.scores["character"] = self._score_character(
            financial_data, research_data, nlp_data
        )
        self.scores["capacity"] = self._score_capacity(financial_data)
        self.scores["capital"] = self._score_capital(financial_data)
        self.scores["collateral"] = self._score_collateral(financial_data)
        self.scores["conditions"] = self._score_conditions(
            research_data, nlp_data
        )

        # Weighted overall score
        self.overall_score = sum(
            self.scores[c] * self.WEIGHTS[c] for c in self.WEIGHTS
        )

        # Cross-verification penalty
        cv_score = cross_verification.get("reconciliation_score", 100)
        cv_penalty = max(0, (100 - cv_score) * 0.15)
        self.overall_score = max(0, self.overall_score - cv_penalty)

        # Qualitative adjustment
        qual_adjustment = 0
        if qualitative_data:
            qual_adjustment = qualitative_data.get("score_adjustment", 0)
            self.overall_score = max(0, min(100, self.overall_score + qual_adjustment))

        # Compile Early Warning Signals
        early_warning_signals = self._compute_early_warning_signals(
            financial_data, nlp_data, cross_verification
        )

        recommendation = self._generate_recommendation()

        return {
            "scores": self.scores,
            "weights": self.WEIGHTS,
            "overall_score": round(self.overall_score, 2),
            "details": self.details,
            "cross_verification_penalty": round(cv_penalty, 2),
            "qualitative_adjustment": qual_adjustment,
            "recommendation": recommendation,
            "risk_grade": self._get_risk_grade(),
            "early_warning_signals": early_warning_signals,
        }

    # ═══════════════════════════════════════════════════════════════
    #  INDIVIDUAL C SCORING
    # ═══════════════════════════════════════════════════════════════

    def _score_character(self, financial: dict, research: dict, nlp: dict) -> float:
        """Score borrower character: reputation, track record, integrity."""
        score = 70  # base score
        factors = []

        # Promoter reputation from research
        sentiment = nlp.get("news_sentiment", {})
        # Handle None if the key exists but value is None
        sent_score = sentiment.get("overall_score")
        if sent_score is None:
            sent_score = 0

        if sent_score > 0.3:
            score += 15
            factors.append("Positive media sentiment (+15)")
        elif sent_score < -0.6:
            score -= 35
            factors.append(f"Critical media sentiment (-35, score: {sent_score:.2f})")
        elif sent_score < -0.3:
            score -= 20
            factors.append(f"Negative media sentiment (-20, score: {sent_score:.2f})")

        # Risk signals
        risk = nlp.get("risk_signals", {})
        risk_level = risk.get("risk_level", "LOW")
        if risk_level == "CRITICAL":
            score -= 40
            factors.append("Critical risk signals detected (-40)")
        elif risk_level == "HIGH":
            score -= 25
            factors.append("High risk signals (-25)")
        elif risk_level == "MODERATE":
            score -= 10
            factors.append("Moderate risk signals (-10)")

        # Litigation count from research
        legal = research.get("findings", {}).get("legal", [])
        if len(legal) > 5:
            score -= 15
            factors.append(f"Multiple litigation findings ({len(legal)}) (-15)")
        elif len(legal) > 2:
            score -= 8
            factors.append(f"Some litigation findings ({len(legal)}) (-8)")

        score = max(0, min(100, score))
        self.details["character"] = {
            "score": round(score, 2),
            "factors": factors,
            "sentiment_score": round(sent_score, 3),
            "risk_level": risk_level,
        }
        return score

    def _score_capacity(self, financial: dict) -> float:
        """Score repayment capacity: revenue, cash flow, DSCR, ICR."""
        score = 60
        factors = []

        metrics = financial.get("metrics", financial)

        # Revenue trend
        revenue = self._get_metric(metrics, "revenue")
        if revenue:
            rev_growth = self._get_metric(metrics, "revenue", "growth_pct")
            if rev_growth and rev_growth > 10:
                score += 15
                factors.append(f"Strong revenue growth ({rev_growth}%) (+15)")
            elif rev_growth and rev_growth > 0:
                score += 5
                factors.append(f"Positive revenue growth ({rev_growth}%) (+5)")
            elif rev_growth and rev_growth < -5:
                score -= 15
                factors.append(f"Declining revenue ({rev_growth}%) (-15)")

        # DSCR (Debt Service Coverage Ratio)
        dscr = self._get_metric(metrics, "dscr")
        if dscr:
            if dscr >= 2.0:
                score += 15
                factors.append(f"Strong DSCR ({dscr:.2f}) (+15)")
            elif dscr >= 1.5:
                score += 8
                factors.append(f"Adequate DSCR ({dscr:.2f}) (+8)")
            elif dscr >= 1.0:
                factors.append(f"Marginal DSCR ({dscr:.2f}) (+0)")
            else:
                score -= 25
                factors.append(f"Weak DSCR ({dscr:.2f}) - below 1.0 (-25)")

        # Interest Coverage Ratio
        icr = self._get_metric(metrics, "interest_coverage_ratio")
        if icr:
            if icr >= 3.0:
                score += 10
                factors.append(f"Strong ICR ({icr:.2f}) (+10)")
            elif icr < 1.5:
                score -= 15
                factors.append(f"Weak ICR ({icr:.2f}) (-15)")

        # PAT Margin
        pat = self._get_metric(metrics, "pat")
        if isinstance(pat, dict):
            margin = pat.get("margin_pct", 0)
        else:
            margin = self._get_metric(metrics, "pat", "margin_pct") or 0

        if margin:
            if margin > 10:
                score += 10
                factors.append(f"Healthy PAT margin ({margin}%) (+10)")
            elif margin < 0:
                score -= 20
                factors.append(f"Loss-making company (PAT margin: {margin}%) (-20)")

        score = max(0, min(100, score))
        self.details["capacity"] = {"score": round(score, 2), "factors": factors}
        return score

    def _score_capital(self, financial: dict) -> float:
        """Score capital structure: net worth, D/E ratio, tangible NW."""
        score = 60
        factors = []
        metrics = financial.get("metrics", financial)

        # Debt-to-Equity ratio
        de_ratio = self._get_metric(metrics, "debt_equity_ratio")
        if de_ratio is not None:
            if de_ratio < 1.0:
                score += 20
                factors.append(f"Conservative D/E ratio ({de_ratio:.2f}) (+20)")
            elif de_ratio < 2.0:
                score += 5
                factors.append(f"Moderate D/E ratio ({de_ratio:.2f}) (+5)")
            elif de_ratio < 3.0:
                score -= 10
                factors.append(f"High D/E ratio ({de_ratio:.2f}) (-10)")
            else:
                score -= 25
                factors.append(f"Very high D/E ratio ({de_ratio:.2f}) (-25)")

        # Current ratio
        cr = self._get_metric(metrics, "current_ratio")
        if cr is not None:
            if cr >= 1.5:
                score += 10
                factors.append(f"Healthy current ratio ({cr:.2f}) (+10)")
            elif cr < 1.0:
                score -= 15
                factors.append(f"Poor current ratio ({cr:.2f}) - liquidity risk (-15)")

        # Net worth
        nw = self._get_metric(metrics, "net_worth")
        if nw and isinstance(nw, (int, float)) and nw > 0:
            score += 5
            factors.append(f"Positive net worth (₹{nw} Cr) (+5)")
        elif nw and isinstance(nw, dict) and nw.get("value", 0) > 0:
            score += 5
            factors.append(f"Positive net worth (₹{nw['value']} Cr) (+5)")

        score = max(0, min(100, score))
        self.details["capital"] = {"score": round(score, 2), "factors": factors}
        return score

    def _score_collateral(self, financial: dict) -> float:
        """Score collateral adequacy."""
        score = 65  # base assumption
        factors = []
        metrics = financial.get("metrics", financial)

        total_assets = self._get_metric(metrics, "total_assets")
        total_debt = self._get_metric(metrics, "total_debt")

        if total_assets and total_debt:
            a_val = total_assets.get("value", total_assets) if isinstance(total_assets, dict) else total_assets
            d_val = total_debt.get("value", total_debt) if isinstance(total_debt, dict) else total_debt

            if a_val and d_val and d_val > 0:
                coverage = a_val / d_val
                if coverage >= 2.0:
                    score += 20
                    factors.append(f"Strong asset coverage ({coverage:.2f}x) (+20)")
                elif coverage >= 1.5:
                    score += 10
                    factors.append(f"Adequate asset coverage ({coverage:.2f}x) (+10)")
                elif coverage < 1.0:
                    score -= 20
                    factors.append(f"Insufficient asset coverage ({coverage:.2f}x) (-20)")

        score = max(0, min(100, score))
        self.details["collateral"] = {"score": round(score, 2), "factors": factors}
        return score

    def _score_conditions(self, research: dict, nlp: dict) -> float:
        """Score market conditions: industry outlook, regulatory environment."""
        score = 65
        factors = []

        # Sector news sentiment
        sector_findings = research.get("findings", {}).get("sector", [])
        if sector_findings:
            sector_texts = [f.get("snippet", "") + " " + f.get("content", "") for f in sector_findings]
            from core.nlp_engine import analyze_sentiment
            for text in sector_texts[:3]:
                s = analyze_sentiment(text)
                if s["label"] == "POSITIVE":
                    score += 5
                    factors.append("Positive sector outlook (+5)")
                elif s["label"] == "NEGATIVE":
                    score -= 8
                    factors.append("Negative sector outlook (-8)")
                break  # Use first finding

        # Regulatory risk
        reg_findings = research.get("findings", {}).get("regulatory", [])
        if len(reg_findings) > 3:
            score -= 15
            factors.append(f"Multiple regulatory findings ({len(reg_findings)}) (-15)")
        elif len(reg_findings) > 0:
            score -= 5
            factors.append(f"Some regulatory findings ({len(reg_findings)}) (-5)")
        else:
            score += 5
            factors.append("No regulatory concerns found (+5)")

        if not factors:
            factors.append("Baseline conditions assessment applied")

        score = max(0, min(100, score))
        self.details["conditions"] = {"score": round(score, 2), "factors": factors}
        return score

    # ═══════════════════════════════════════════════════════════════
    #  RECOMMENDATION
    # ═══════════════════════════════════════════════════════════════

    def _generate_recommendation(self) -> dict:
        """Generate loan recommendation based on overall score."""
        score = self.overall_score

        if score >= Config.CREDIT_SCORE_EXCELLENT:
            decision = "APPROVE"
            risk_premium = Config.RISK_PREMIUM_MAP["LOW"]
            max_loan_multiplier = 3.0  # 3x of net worth
            tenor = "5 Years"
        elif score >= Config.CREDIT_SCORE_GOOD:
            decision = "APPROVE"
            risk_premium = Config.RISK_PREMIUM_MAP["MODERATE"]
            max_loan_multiplier = 2.0
            tenor = "3 Years"
        elif score >= Config.CREDIT_SCORE_FAIR:
            decision = "REFER"
            risk_premium = Config.RISK_PREMIUM_MAP["HIGH"]
            max_loan_multiplier = 1.0
            tenor = "1 Year"
        else:
            decision = "REJECT"
            risk_premium = Config.RISK_PREMIUM_MAP["VERY_HIGH"]
            max_loan_multiplier = 0
            tenor = "None"

        interest_rate = Config.BASE_INTEREST_RATE + (risk_premium / 100)

        # Build rejection/refer reasons
        reasons = []
        for c, detail in self.details.items():
            if detail["score"] < 40:
                reasons.append(f"Weak {c.title()} score ({detail['score']}/100)")
            for factor in detail.get("factors", []):
                if any(neg in factor.lower() for neg in ["critical", "weak", "high risk", "loss"]):
                    reasons.append(factor)

        return {
            "decision": decision,
            "interest_rate_pct": round(interest_rate, 2),
            "risk_premium_bps": risk_premium,
            "max_loan_multiplier": max_loan_multiplier,
            "recommended_tenor": tenor,
            "key_reasons": reasons[:5],
            "conditions": self._suggest_conditions(score),
        }

    def _suggest_conditions(self, score: float) -> list:
        """Suggest loan conditions based on score."""
        conditions = []
        if score < 80:
            conditions.append("Quarterly review of financial statements")
        if score < 60:
            conditions.append("Monthly stock/receivables statements")
            conditions.append("Personal guarantee of promoters")
        if score < 40:
            conditions.append("Additional collateral security required")
            conditions.append("Restriction on dividend payment")
        if self.details.get("character", {}).get("score", 100) < 50:
            conditions.append("Enhanced due diligence on promoter activities")
        return conditions

    def _get_risk_grade(self) -> str:
        """Map score to risk grade."""
        s = self.overall_score
        if s >= 80:
            return "IC-1 (Minimal Risk)"
        elif s >= 70:
            return "IC-2 (Low Risk)"
        elif s >= 60:
            return "IC-3 (Moderate Risk)"
        elif s >= 50:
            return "IC-4 (Acceptable Risk)"
        elif s >= 40:
            return "IC-5 (Watch)"
        elif s >= 30:
            return "IC-6 (Substandard)"
        elif s >= 20:
            return "IC-7 (Doubtful)"
        else:
            return "IC-8 (Loss)"

    @staticmethod
    def _get_metric(data: dict, key: str, sub_key: str = None):
        """Safely extract a metric value from nested dict."""
        val = data.get(key)
        if val is None:
            return None
        if sub_key and isinstance(val, dict):
            val = val.get(sub_key)
        elif isinstance(val, dict) and "value" in val and sub_key is None:
            val = val["value"]
            
        if val in ("N/A", "Not Available", None):
            return None
        return val

    def _compute_early_warning_signals(self, financial: dict, nlp: dict, cv: dict) -> list:
        """Extract high-priority risks into actionable Early Warning Signals."""
        ews = []
        metrics = financial.get("metrics", financial)

        # 1. Cross Verification mismatch
        cv_score = cv.get("reconciliation_score", 100)
        discrepancies = cv.get("discrepancies", [])
        if cv_score < 70 or discrepancies:
            ews.append({
                "title": f"Major Data Discrepancy (Match Score: {cv_score}%)",
                "detail": "Significant divergence detected between bank statements and GST/Financial filings."
            })

        # 2. Financial stress metrics
        dscr = self._get_metric(metrics, "dscr")
        if dscr and dscr < 1.0:
            ews.append({
                "title": f"Severe Liquidity Risk (DSCR: {dscr})",
                "detail": "Debt Service Coverage Ratio is below 1, indicating potential inability to service current debt obligations."
            })

        de_ratio = self._get_metric(metrics, "debt_equity_ratio")
        if de_ratio and de_ratio > 3.0:
            ews.append({
                "title": f"High Leverage Warning (D/E Ratio: {de_ratio})",
                "detail": "Borrower is highly leveraged. Capital buffer is inadequate to absorb potential shocks."
            })

        # 3. NLP & Web Intelligence Risk
        risk = nlp.get("risk_signals", {})
        risk_level = risk.get("risk_level", "LOW")
        if risk_level in ["HIGH", "CRITICAL"]:
            # extract the top signal
            signals = risk.get("signals", [])
            detail = "Critical adverse media or legal actions flagged in secondary research."
            if signals:
                detail = f"Identified '{signals[0].get('type', 'risk')}' markers in public domain."
            ews.append({
                "title": f"{risk_level.title()} External Risk Priority",
                "detail": detail
            })
            
        return ews
