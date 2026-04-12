"""
Cross-Verifier - Pillar 1
===========================
GST vs Bank Statement reconciliation engine.
Detects circular trading, revenue inflation, and discrepancies.
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class CrossVerifier:
    """Cross-verify GST filings against bank statements to detect fraud."""

    def __init__(self):
        self.gst_data = None
        self.bank_data = None
        self.discrepancies = []
        self.risk_flags = []
        self.reconciliation_score = 100  # starts at 100, decreases with discrepancies

    def load_gst_data(self, data: dict):
        """Load parsed GST filing data."""
        if "preview" in data:
            self.gst_data = pd.DataFrame(data["preview"])
        elif "data" in data:
            self.gst_data = pd.DataFrame(data["data"])
        logger.info(f"Loaded GST data: {len(self.gst_data) if self.gst_data is not None else 0} rows")

    def load_bank_data(self, data: dict):
        """Load parsed bank statement data."""
        if "preview" in data:
            self.bank_data = pd.DataFrame(data["preview"])
        elif "data" in data:
            self.bank_data = pd.DataFrame(data["data"])
        logger.info(f"Loaded bank data: {len(self.bank_data) if self.bank_data is not None else 0} rows")

    def run_verification(self) -> dict:
        """Run complete cross-verification pipeline."""
        results = {
            "status": "complete",
            "checks_performed": [],
            "discrepancies": [],
            "risk_flags": [],
            "reconciliation_score": 100,
            "summary": "",
        }

        # ── Check 1: Revenue Reconciliation ──
        rev_check = self._check_revenue_reconciliation()
        results["checks_performed"].append(rev_check)
        if rev_check.get("discrepancy"):
            results["discrepancies"].append(rev_check)

        # ── Check 2: Circular Trading Detection ──
        circular_check = self._detect_circular_trading()
        results["checks_performed"].append(circular_check)
        if circular_check.get("risk_detected"):
            results["risk_flags"].append(circular_check)

        # ── Check 3: Revenue Inflation ──
        inflation_check = self._check_revenue_inflation()
        results["checks_performed"].append(inflation_check)
        if inflation_check.get("inflation_detected"):
            results["risk_flags"].append(inflation_check)

        # ── Check 4: Cash Flow Consistency ──
        cf_check = self._check_cash_flow_consistency()
        results["checks_performed"].append(cf_check)

        # ── Check 5: GSTR-2A vs GSTR-3B Mismatch ──
        gstr_check = self._check_gstr_mismatch()
        results["checks_performed"].append(gstr_check)
        if gstr_check.get("mismatch_detected"):
            results["risk_flags"].append(gstr_check)

        # Calculate final score
        penalty = len(results["discrepancies"]) * 10 + len(results["risk_flags"]) * 15
        results["reconciliation_score"] = max(0, 100 - penalty)
        self.reconciliation_score = results["reconciliation_score"]

        # Generate summary
        if results["reconciliation_score"] >= 80:
            results["summary"] = "Cross-verification shows strong consistency between GST filings and bank statements. No major discrepancies detected."
        elif results["reconciliation_score"] >= 50:
            results["summary"] = f"Cross-verification reveals {len(results['discrepancies'])} discrepancies and {len(results['risk_flags'])} risk flags. Moderate concerns requiring further investigation."
        else:
            results["summary"] = f"CRITICAL: Cross-verification reveals significant inconsistencies. {len(results['risk_flags'])} risk flags detected. High risk of data manipulation or fraud."

        return results

    def _check_revenue_reconciliation(self) -> dict:
        """Compare GST-reported revenue against bank credit entries."""
        check = {
            "check_name": "Revenue Reconciliation (GST vs Bank Credits)",
            "description": "Compare total revenue reported in GST filings against total credits in bank statement",
            "discrepancy": False,
        }

        gst_revenue = self._get_gst_revenue()
        bank_credits = self._get_bank_credits()

        if gst_revenue is not None and bank_credits is not None:
            variance = abs(gst_revenue - bank_credits) / max(gst_revenue, 1) * 100
            check["gst_revenue"] = round(gst_revenue, 2)
            check["bank_credits"] = round(bank_credits, 2)
            check["variance_pct"] = round(variance, 2)

            if variance > 20:
                check["discrepancy"] = True
                check["severity"] = "HIGH"
                check["detail"] = f"Revenue variance of {variance:.1f}% between GST ({gst_revenue:,.0f}) and bank credits ({bank_credits:,.0f})"
            elif variance > 10:
                check["discrepancy"] = True
                check["severity"] = "MODERATE"
                check["detail"] = f"Revenue variance of {variance:.1f}% - warrants further review"
            else:
                check["detail"] = f"Revenue reconciliation within acceptable range ({variance:.1f}% variance)"
        else:
            check["detail"] = "Insufficient data for revenue reconciliation"
            check["data_available"] = False

        return check

    def _detect_circular_trading(self) -> dict:
        """Detect circular trading patterns in bank statements."""
        check = {
            "check_name": "Circular Trading Detection",
            "description": "Identify suspicious patterns where same amounts cycle through related entities",
            "risk_detected": False,
        }

        if self.bank_data is None or self.bank_data.empty:
            check["detail"] = "No bank data available for circular trading analysis"
            return check

        try:
            # Look for same-amount credits and debits within short timeframes
            credit_col = self._find_column(self.bank_data, ["credit", "deposit"])
            debit_col = self._find_column(self.bank_data, ["debit", "withdrawal"])

            if credit_col and debit_col:
                credits = pd.to_numeric(self.bank_data[credit_col], errors="coerce").dropna()
                debits = pd.to_numeric(self.bank_data[debit_col], errors="coerce").dropna()

                credits_set = set(credits[credits > 0].values)
                debits_set = set(debits[debits > 0].values)

                # Find matching amounts (potential round-tripping)
                matches = credits_set.intersection(debits_set)
                large_matches = [m for m in matches if m > 100000]  # > 1 Lakh

                if len(large_matches) > 3:
                    check["risk_detected"] = True
                    check["severity"] = "HIGH"
                    check["matching_amounts"] = len(large_matches)
                    check["detail"] = f"Found {len(large_matches)} large matching credit-debit amounts (>₹1L). Potential circular trading."
                elif len(large_matches) > 0:
                    check["matching_amounts"] = len(large_matches)
                    check["detail"] = f"Found {len(large_matches)} matching amounts - within normal range"
                else:
                    check["detail"] = "No circular trading patterns detected"
            else:
                check["detail"] = "Could not identify credit/debit columns"
        except Exception as e:
            check["detail"] = f"Analysis error: {str(e)}"

        return check

    def _check_revenue_inflation(self) -> dict:
        """Statistical check for revenue inflation patterns."""
        check = {
            "check_name": "Revenue Inflation Analysis",
            "description": "Statistical analysis to detect anomalous revenue patterns",
            "inflation_detected": False,
        }

        gst_revenue_series = self._get_gst_monthly_revenue()

        if gst_revenue_series is not None and len(gst_revenue_series) > 3:
            mean_rev = gst_revenue_series.mean()
            std_rev = gst_revenue_series.std()
            cv = std_rev / mean_rev if mean_rev > 0 else 0  # Coefficient of variation

            check["mean_revenue"] = round(float(mean_rev), 2)
            check["std_deviation"] = round(float(std_rev), 2)
            check["coefficient_of_variation"] = round(float(cv), 4)

            # Check for suspicious patterns
            if cv > 0.5:
                check["inflation_detected"] = True
                check["severity"] = "MODERATE"
                check["detail"] = f"High revenue volatility (CV: {cv:.2f}). Possible revenue manipulation in specific months."
            else:
                check["detail"] = f"Revenue pattern within normal volatility range (CV: {cv:.2f})"

            # Check for monotonic increase (suspiciously smooth growth)
            diff = gst_revenue_series.diff().dropna()
            if len(diff) > 3 and all(diff > 0):
                check["inflation_detected"] = True
                check["severity"] = "LOW"
                check["detail"] += " Perfectly monotonic revenue growth detected - uncommon in practice."
        else:
            check["detail"] = "Insufficient monthly data for inflation analysis"

        return check

    def _check_cash_flow_consistency(self) -> dict:
        """Check if cash flows are consistent with reported operations."""
        check = {
            "check_name": "Cash Flow Consistency",
            "description": "Verify that bank statement cash flows align with reported operations",
        }

        bank_credits = self._get_bank_credits()
        bank_debits = self._get_bank_debits()

        if bank_credits is not None and bank_debits is not None:
            net_flow = bank_credits - bank_debits
            flow_ratio = bank_debits / bank_credits if bank_credits > 0 else 0

            check["total_inflows"] = round(bank_credits, 2)
            check["total_outflows"] = round(bank_debits, 2)
            check["net_flow"] = round(net_flow, 2)
            check["outflow_ratio"] = round(flow_ratio, 4)

            if flow_ratio > 0.95:
                check["detail"] = "Very high outflow ratio - company is deploying almost all received funds"
            elif flow_ratio < 0.5:
                check["detail"] = "Low outflow ratio - company is accumulating cash, positive sign"
            else:
                check["detail"] = "Cash flow pattern appears normal"
        else:
            check["detail"] = "Insufficient bank data for cash flow analysis"

        return check

    def _check_gstr_mismatch(self) -> dict:
        """Check for GSTR-2A vs GSTR-3B discrepancies."""
        check = {
            "check_name": "GSTR-2A vs GSTR-3B Mismatch Check",
            "description": "Compare input tax credit claimed (3B) against auto-populated (2A)",
            "mismatch_detected": False,
        }

        if self.gst_data is None or self.gst_data.empty:
            check["detail"] = "No GST data available for GSTR mismatch analysis"
            return check

        cols_lower = {str(c).lower(): c for c in self.gst_data.columns}

        gstr2a_col = None
        gstr3b_col = None
        for key, col in cols_lower.items():
            if "2a" in key or "2b" in key:
                gstr2a_col = col
            if "3b" in key:
                gstr3b_col = col

        if gstr2a_col and gstr3b_col:
            try:
                val_2a = pd.to_numeric(self.gst_data[gstr2a_col], errors="coerce").sum()
                val_3b = pd.to_numeric(self.gst_data[gstr3b_col], errors="coerce").sum()
                diff = abs(val_3b - val_2a)
                diff_pct = diff / max(val_2a, 1) * 100

                check["gstr_2a_total"] = round(float(val_2a), 2)
                check["gstr_3b_total"] = round(float(val_3b), 2)
                check["difference_pct"] = round(float(diff_pct), 2)

                if diff_pct > 10:
                    check["mismatch_detected"] = True
                    check["severity"] = "HIGH" if diff_pct > 25 else "MODERATE"
                    check["detail"] = f"ITC mismatch: GSTR-3B ({val_3b:,.0f}) vs GSTR-2A ({val_2a:,.0f}) - {diff_pct:.1f}% variance"
                else:
                    check["detail"] = f"GSTR-2A/3B within acceptable variance ({diff_pct:.1f}%)"
            except Exception as e:
                check["detail"] = f"Could not compare GSTR variants: {str(e)}"
        else:
            check["detail"] = "GSTR-2A / GSTR-3B columns not found in data"

        return check

    # ── Helper methods ──

    def _get_gst_revenue(self) -> Optional[float]:
        if self.gst_data is None or self.gst_data.empty:
            return None
        rev_col = self._find_column(self.gst_data, ["taxable", "value", "amount", "total", "revenue"])
        if rev_col:
            return float(pd.to_numeric(self.gst_data[rev_col], errors="coerce").sum())
        return None

    def _get_gst_monthly_revenue(self):
        if self.gst_data is None or self.gst_data.empty:
            return None
        rev_col = self._find_column(self.gst_data, ["taxable", "value", "amount", "total", "revenue"])
        if rev_col:
            return pd.to_numeric(self.gst_data[rev_col], errors="coerce").dropna()
        return None

    def _get_bank_credits(self) -> Optional[float]:
        if self.bank_data is None or self.bank_data.empty:
            return None
        col = self._find_column(self.bank_data, ["credit", "deposit"])
        if col:
            return float(pd.to_numeric(self.bank_data[col], errors="coerce").fillna(0).sum())
        return None

    def _get_bank_debits(self) -> Optional[float]:
        if self.bank_data is None or self.bank_data.empty:
            return None
        col = self._find_column(self.bank_data, ["debit", "withdrawal"])
        if col:
            return float(pd.to_numeric(self.bank_data[col], errors="coerce").fillna(0).sum())
        return None

    @staticmethod
    def _find_column(df: pd.DataFrame, keywords: list) -> Optional[str]:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in keywords):
                return col
        return None
