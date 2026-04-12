"""
Credit Analyzer - Structured CAM Analysis Engine
==================================================
Implements the 5-step credit analysis pipeline:
  STEP 1: Entity Classification (Corporate vs NBFC)
  STEP 2: Extract Core Financial Inputs
  STEP 3: Compute Credit Ratios
  STEP 4: Weighted Credit Scoring → Rating
  STEP 5: Anomaly / Flag Detection
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CreditAnalyzer:
    """
    Structured credit analysis engine that produces a
    Comprehensive Credit Appraisal Memo (CAM).
    """

    # ═══════════════════════════════════════════════════════════════
    #  STEP 1 - ENTITY CLASSIFICATION
    # ═══════════════════════════════════════════════════════════════

    NBFC_INDICATORS = [
        "nii", "gnpa_pct", "nnpa_pct", "car_pct",
        "cost_of_funds_pct", "nim_pct",
    ]

    @classmethod
    def classify_entity(cls, metrics: dict) -> dict:
        """
        Determine if the company is a regular corporate or an NBFC /
        Financial Institution based on the presence of NBFC-specific metrics.
        """
        nbfc_hits = 0
        for indicator in cls.NBFC_INDICATORS:
            val = metrics.get(indicator)
            if val and val not in (0, 0.0, "Not Available"):
                nbfc_hits += 1

        # Also check for keywords in company name
        company_name = (metrics.get("company_name") or "").lower()
        nbfc_keywords = [
            "capital", "finance", "financial", "bank", "hfc",
            "housing finance", "microfinance", "mfi", "nbfc",
            "lending", "credit", "kinara", "bajaj finserv",
        ]
        name_hit = any(kw in company_name for kw in nbfc_keywords)

        is_nbfc = (nbfc_hits >= 2) or (name_hit and nbfc_hits >= 1) or \
                  (name_hit and (metrics.get("loan_book") or metrics.get("nii")))

        # Check if ai_analyzer explicitly classified it
        ai_entity_type = metrics.get("entity_type", "").lower()
        if ai_entity_type == "nbfc":
            is_nbfc = True
        elif ai_entity_type and ai_entity_type != "nbfc":
            is_nbfc = False
            
        entity_type = "NBFC" if is_nbfc else "CORPORATE"
        classification = {
            "entity_type": entity_type,
            "description": "NBFC / Financial Institution" if is_nbfc
                           else "Regular Company (Manufacturing / IT / Services / Startup)",
            "nbfc_indicators_found": nbfc_hits,
            "name_match": name_hit,
        }
        logger.info(f"Entity classified as: {entity_type}")
        return classification

    # ═══════════════════════════════════════════════════════════════
    #  STEP 2 - EXTRACT CORE FINANCIAL INPUTS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def extract_inputs(metrics: dict) -> dict:
        """
        Structure raw financial metrics into the standard input set
        required for credit analysis. Values in INR Crores unless noted.
        Marks missing values as "Not Available".
        """
        def _val(key):
            """Extract numeric value, handling nested dicts like {value: X, unit: 'Cr'}."""
            v = _get_value(metrics, key)
            if v is None:
                return "Not Available"
            # Accept 0 as a valid numeric value (e.g. zero debt)
            # Only mark as "Not Available" when truly missing
            return v

        def _pct(key):
            v = metrics.get(key)
            if v is None or v == 0:
                return "Not Available"
            return v

        # --- Extract revenue value for fallback computations ---
        revenue_val = _get_value(metrics, "revenue")

        # --- PAT: try direct extraction, then fallback ---
        pat_val = _get_value(metrics, "pat")
        if pat_val is None:
            # Fallback: compute from revenue * margin_pct
            pat_obj = metrics.get("pat")
            if isinstance(pat_obj, dict):
                margin = pat_obj.get("margin_pct")
                if margin is not None and revenue_val:
                    pat_val = round(revenue_val * margin / 100, 2)

        # --- Net Worth: try direct extraction, then multiple fallbacks ---
        nw_val = _get_value(metrics, "net_worth")
        if nw_val is None or nw_val == 0:
            logger.info(f"Net Worth direct extraction returned: {nw_val}, trying fallbacks...")
            nw_val = None  # Reset 0 to None to trigger fallbacks
        if nw_val is None:
            # Fallback 1: from total_equity (some documents use this label)
            nw_val = _get_value(metrics, "total_equity")
            if nw_val:
                logger.info(f"Net Worth fallback 1 (total_equity): {nw_val}")
        if nw_val is None:
            # Fallback 2: from tangible_net_worth
            nw_val = _get_value(metrics, "tangible_net_worth")
            if nw_val:
                logger.info(f"Net Worth fallback 2 (tangible_net_worth): {nw_val}")
        if nw_val is None:
            # Fallback 3: compute from total_debt / debt_equity_ratio
            td = _get_value(metrics, "total_debt")
            de = metrics.get("debt_equity_ratio")
            if td and de and isinstance(de, (int, float)) and de > 0:
                nw_val = round(td / de, 2)
                logger.info(f"Net Worth fallback 3 (total_debt/D-E): {nw_val}")
        if nw_val is None:
            # Fallback 4: total_assets - total_debt (accounting identity)
            ta = _get_value(metrics, "total_assets")
            td = _get_value(metrics, "total_debt")
            if ta and td and isinstance(ta, (int, float)) and isinstance(td, (int, float)):
                nw_val = round(ta - td, 2)
                logger.info(f"Net Worth fallback 4 (total_assets - total_debt): {nw_val}")

        # --- EBITDA: try direct, then PPOP for NBFCs ---
        ebitda_val = _get_value(metrics, "ebitda")
        if ebitda_val is None:
            ppop_val = _get_value(metrics, "ppop")
            if ppop_val is not None:
                ebitda_val = ppop_val

        # Common inputs for ALL companies
        inputs = {
            "total_revenue": revenue_val if revenue_val is not None else "Not Available",
            "ebitda": ebitda_val if ebitda_val is not None else "Not Available",
            "ebit": _val("ebit"),
            "net_profit_pat": pat_val if pat_val is not None else "Not Available",
            "total_debt": _val("total_debt"),
            "net_worth": nw_val if nw_val is not None else "Not Available",
            "current_assets": _val("current_assets"),
            "current_liabilities": _val("current_liabilities"),
            "operating_cash_flow": _val("cash_flow_from_operations"),
            "interest_expense": _val("interest_expense"),
        }

        # NBFC-specific inputs
        nii_val = metrics.get("nii")
        nii_dict = nii_val if isinstance(nii_val, dict) else {}

        nbfc_inputs = {
            "loan_book_aum": _val("loan_book"),
            "nii": _val("nii"),
            "nim_pct": nii_dict.get("margin_pct") or _pct("nim_pct"),
            "gnpa_pct": _pct("gnpa_pct"),
            "nnpa_pct": _pct("nnpa_pct"),
            "car_pct": _pct("car_pct"),
            "cost_of_funds_pct": _pct("cost_of_funds_pct"),
            "roa_pct": _pct("roa_pct"),
            "roe_pct": _pct("roe_pct"),
        }


        return {"common": inputs, "nbfc": nbfc_inputs}

    # ═══════════════════════════════════════════════════════════════
    #  STEP 3 - COMPUTE CREDIT RATIOS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def compute_ratios(inputs: dict, entity_type: str = "CORPORATE") -> list:
        """
        Compute six key credit ratios from the extracted inputs.
        Returns a list of dicts with: name, formula, value, interpretation.
        """
        common = inputs["common"]
        ratios = []

        # Helper to safely get a numeric value
        def _num(key):
            v = common.get(key)
            if v == "Not Available" or v is None or v == "N/A":
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        total_debt = _num("total_debt")
        net_worth = _num("net_worth")
        ebit = _num("ebit")
        interest = _num("interest_expense")
        ocf = _num("operating_cash_flow")
        current_assets = _num("current_assets")
        current_liabilities = _num("current_liabilities")
        ebitda = _num("ebitda")
        revenue = _num("total_revenue")
        pat = _num("net_profit_pat")
        is_nbfc = entity_type.upper() in ("NBFC", "BANK", "HFC", "MFI")

        # 1. Debt-to-Equity
        if total_debt is not None and net_worth is not None and net_worth > 0:
            de = round(total_debt / net_worth, 2)
            if de < 1:
                interp = "Low leverage - strong equity cushion."
            elif de <= 2:
                interp = "Moderate leverage - within acceptable limits."
            elif de <= 4:
                interp = "High leverage - elevated financial risk."
            else:
                interp = "Very high leverage - significant default risk."
            ratios.append({
                "name": "Debt-to-Equity (D/E)",
                "formula": "Total Debt / Net Worth",
                "value": de,
                "interpretation": interp,
            })
        else:
            ratios.append({
                "name": "Debt-to-Equity (D/E)",
                "formula": "Total Debt / Net Worth",
                "value": "N/A",
                "interpretation": "Cannot compute - missing Total Debt or Net Worth.",
            })

        # 2. Interest Coverage Ratio (ICR)
        # Compute for all entity types if data exists
        if ebit is not None and interest is not None and interest > 0:
            icr = round(ebit / interest, 2)
            if icr >= 3:
                interp = "Strong interest coverage - comfortable debt servicing."
            elif icr >= 1.5:
                interp = "Adequate interest coverage."
            else:
                interp = "Weak interest coverage - debt servicing risk."
            if is_nbfc:
                interp += " (Note: ICR interpretation differs for NBFCs.)"
            ratios.append({
                "name": "Interest Coverage Ratio (ICR)",
                "formula": "EBIT / Interest Expense",
                "value": icr,
                "interpretation": interp,
            })
        else:
            ratios.append({
                "name": "Interest Coverage Ratio (ICR)",
                "formula": "EBIT / Interest Expense",
                "value": "N/A",
                "interpretation": "Cannot compute - missing EBIT or Interest Expense.",
            })

        # 3. DSCR
        if ocf is not None and total_debt is not None and total_debt > 0:
            # Using Total Debt as proxy for total debt service
            dscr = round(ocf / total_debt, 2)
            if dscr >= 1.5:
                interp = "Strong debt service coverage - low repayment risk."
            elif dscr >= 1.0:
                interp = "Adequate but thin debt service coverage."
            else:
                interp = "Insufficient cash flow to service debt obligations."
            if is_nbfc:
                interp += " (Note: DSCR interpretation differs for NBFCs.)"
            ratios.append({
                "name": "DSCR",
                "formula": "Operating Cash Flow / Total Debt Service",
                "value": dscr,
                "interpretation": interp,
            })
        else:
            ratios.append({
                "name": "DSCR",
                "formula": "Operating Cash Flow / Total Debt Service",
                "value": "N/A",
                "interpretation": "Cannot compute - missing Operating Cash Flow or Total Debt.",
            })

        # 4. Current Ratio
        if current_assets is not None and current_liabilities is not None and current_liabilities > 0:
            cr = round(current_assets / current_liabilities, 2)
            if cr >= 2:
                interp = "Strong liquidity position - ample short-term asset cover."
            elif cr >= 1:
                interp = "Adequate liquidity but limited buffer."
            else:
                interp = "Liquidity stress - current liabilities exceed current assets."
            if is_nbfc:
                interp += " (Note: Current Ratio interpretation differs for NBFCs.)"
            ratios.append({
                "name": "Current Ratio",
                "formula": "Current Assets / Current Liabilities",
                "value": cr,
                "interpretation": interp,
            })
        else:
            ratios.append({
                "name": "Current Ratio",
                "formula": "Current Assets / Current Liabilities",
                "value": "N/A",
                "interpretation": "Cannot compute - missing Current Assets or Current Liabilities.",
            })

        # 5. EBITDA / PPOP Margin
        ratio_label = "EBITDA Margin"
        if is_nbfc and ebitda is not None:
            ratio_label = "PPOP / EBITDA Margin"
        if ebitda is not None and revenue is not None and revenue > 0:
            margin = round(ebitda / revenue * 100, 2)
            if margin > 20:
                interp = "Excellent profitability - strong operating efficiency."
            elif margin >= 10:
                interp = "Adequate margins - reasonable operating performance."
            else:
                interp = "Thin margins - limited buffer against cost pressures."
            ratios.append({
                "name": ratio_label,
                "formula": "EBITDA / Revenue x 100",
                "value": margin,
                "display": f"{margin}%",
                "interpretation": interp,
            })
        else:
            ratios.append({
                "name": ratio_label,
                "formula": "EBITDA / Revenue x 100",
                "value": "N/A",
                "interpretation": "Cannot compute - missing EBITDA or Revenue.",
            })

        # 6. Net Profit Margin
        if pat is not None and revenue is not None and revenue > 0:
            npm = round(pat / revenue * 100, 2)
            if npm > 15:
                interp = "Excellent net profitability."
            elif npm > 5:
                interp = "Healthy net margins."
            elif npm >= 0:
                interp = "Thin net margins - vulnerable to shocks."
            else:
                interp = "Net loss - profitability concerns."
            ratios.append({
                "name": "Net Profit Margin",
                "formula": "PAT / Revenue × 100",
                "value": npm,
                "display": f"{npm}%",
                "interpretation": interp,
            })
        else:
            ratios.append({
                "name": "Net Profit Margin",
                "formula": "PAT / Revenue × 100",
                "value": "N/A",
                "interpretation": "Cannot compute - missing PAT or Revenue.",
            })

        return ratios

    # ═══════════════════════════════════════════════════════════════
    #  STEP 4 - WEIGHTED CREDIT SCORING
    # ═══════════════════════════════════════════════════════════════

    # Industry risk classification
    INDUSTRY_RISK = {
        # Low risk
        "it": "LOW", "technology": "LOW", "software": "LOW",
        "pharma": "LOW", "pharmaceutical": "LOW", "fmcg": "LOW",
        "healthcare": "LOW", "fintech": "LOW",
        # Medium risk
        "manufacturing": "MEDIUM", "retail": "MEDIUM", "auto": "MEDIUM",
        "automotive": "MEDIUM", "textiles": "MEDIUM", "nbfc": "MEDIUM",
        "finance": "MEDIUM", "financial": "MEDIUM", "banking": "MEDIUM",
        "cement": "MEDIUM", "chemicals": "MEDIUM",
        # High risk
        "real estate": "HIGH", "realty": "HIGH", "construction": "HIGH",
        "mining": "HIGH", "infrastructure": "HIGH", "power": "HIGH",
        "steel": "HIGH", "metals": "HIGH", "telecom": "HIGH",
        "airlines": "HIGH", "hospitality": "HIGH",
    }

    @classmethod
    def compute_credit_score(cls, ratios: list, entity_type: str,
                              company_name: str = "", metrics: dict = None) -> dict:
        """
        Compute a weighted credit score out of 100.

        For NBFC/Bank: 5-pillar framework from IntelliCredit Framework doc
          Profitability (25%) | Asset Quality (25%) | Leverage & Solvency (20%) | Growth (15%) | Efficiency (15%)

        For Corporate:
          Leverage (D/E) 25% | Profitability (EBITDA Margin) 20% | Liquidity 20% | Cash Flow (DSCR) 20% | Industry Risk 15%
        """
        metrics = metrics or {}
        is_nbfc = entity_type.upper() in ("NBFC", "BANK", "HFC", "MFI")

        if is_nbfc:
            return cls._score_nbfc(ratios, company_name, metrics)
        else:
            return cls._score_corporate(ratios, company_name, metrics)

    @classmethod
    def _score_nbfc(cls, ratios: list, company_name: str, metrics: dict) -> dict:
        """
        NBFC 5-Pillar Scoring Model (IntelliCredit Framework):
        1. Profitability  25% — PAT Margin + ROE
        2. Asset Quality  25% — GNPA% + PCR%
        3. Leverage/Solvency 20% — D/E + CRAR (CAR%)
        4. Growth         15% — AUM/Revenue Growth
        5. Efficiency     15% — NIM%
        """
        breakdown = []
        # Helper
        def _get(key): return metrics.get(key)
        def _dictval(key): v = metrics.get(key); return v.get("value") if isinstance(v, dict) else v

        # ── 1. Profitability 25% ──
        pat_margin = None
        pat = _dictval("pat")
        revenue = _dictval("revenue")
        if pat and revenue and revenue > 0:
            pat_margin = round(pat / revenue * 100, 2)
        roe = _get("roe_pct")
        prof_score = 50  # neutral default
        if pat_margin is not None:
            if pat_margin > 15:   prof_score = 100
            elif pat_margin > 10: prof_score = 80
            elif pat_margin > 5:  prof_score = 60
            elif pat_margin > 0:  prof_score = 40
            else:                 prof_score = 20
        if roe:
            roe_score = 100 if roe > 20 else 80 if roe > 15 else 60 if roe > 10 else 40 if roe > 0 else 20
            prof_score = round((prof_score + roe_score) / 2)
        breakdown.append({
            "factor": "Profitability (PAT Margin + ROE)",
            "weight": 25, "raw_value": f"PAT Margin: {pat_margin}%, ROE: {roe}%",
            "component_score": prof_score, "weighted_contribution": round(prof_score * 0.25, 2),
        })

        # ── 2. Asset Quality 25% ──
        gnpa = _get("gnpa_pct")
        pcr  = _get("pcr_pct")
        aq_score = 60  # default neutral
        if gnpa is not None:
            if gnpa < 1.5:   gnpa_s = 100
            elif gnpa < 3.0: gnpa_s = 80
            elif gnpa < 5.0: gnpa_s = 60
            elif gnpa < 7.0: gnpa_s = 40
            else:            gnpa_s = 20
        else:
            gnpa_s = 60
        if pcr is not None:
            pcr_s = 100 if pcr > 70 else 80 if pcr > 60 else 60 if pcr > 50 else 40
        else:
            pcr_s = 60
        aq_score = round((gnpa_s + pcr_s) / 2)
        breakdown.append({
            "factor": "Asset Quality (GNPA% + PCR%)",
            "weight": 25, "raw_value": f"GNPA: {gnpa}%, PCR: {pcr}%",
            "component_score": aq_score, "weighted_contribution": round(aq_score * 0.25, 2),
        })

        # ── 3. Leverage & Solvency 20% ──
        ratio_dict = {r["name"]: r["value"] for r in ratios}
        de = ratio_dict.get("Debt-to-Equity (D/E)")
        car = _get("car_pct")
        if de is not None and de != "N/A":
            # For NBFCs 3-5x is optimal (leverage needed for lending)
            if 3 <= de <= 5:    de_s = 100
            elif 2 <= de < 3:   de_s = 80
            elif 5 < de <= 7:   de_s = 70
            elif de < 2:        de_s = 60  # under-leveraged
            else:               de_s = 40  # >7x risky
        else:
            de_s = 60
        if car is not None:
            if car > 25:  car_s = 100
            elif car > 20: car_s = 80
            elif car > 15: car_s = 60
            else:          car_s = 20  # regulatory breach risk
        else:
            car_s = 60
        lev_score = round((de_s + car_s) / 2)
        breakdown.append({
            "factor": "Leverage & Solvency (D/E + CRAR)",
            "weight": 20, "raw_value": f"D/E: {de}x, CRAR: {car}%",
            "component_score": lev_score, "weighted_contribution": round(lev_score * 0.20, 2),
        })

        # ── 4. Growth 15% ──
        rev_growth = None
        rev_obj = metrics.get("revenue")
        if isinstance(rev_obj, dict):
            rev_growth = rev_obj.get("growth_pct")
        if rev_growth is None:
            rev_growth = _get("revenue_growth_pct")
        if rev_growth is not None:
            if rev_growth > 25:   grow_score = 100
            elif rev_growth > 15: grow_score = 80
            elif rev_growth > 8:  grow_score = 65
            elif rev_growth > 0:  grow_score = 50
            else:                 grow_score = 30
        else:
            grow_score = 55  # neutral
        breakdown.append({
            "factor": "Growth (AUM / Revenue YoY %)",
            "weight": 15, "raw_value": f"{rev_growth}%" if rev_growth is not None else "N/A",
            "component_score": grow_score, "weighted_contribution": round(grow_score * 0.15, 2),
        })

        # ── 5. Efficiency 15% — NIM% ──
        nim = _get("nim_pct")
        cof = _get("cost_of_funds_pct")
        if nim is not None:
            if nim > 8:   eff_score = 100
            elif nim > 6: eff_score = 80
            elif nim > 4: eff_score = 60
            else:         eff_score = 40
        elif cof is not None:
            eff_score = 80 if cof < 8 else 60 if cof < 11 else 40
        else:
            eff_score = 55
        breakdown.append({
            "factor": "Efficiency (NIM%)",
            "weight": 15, "raw_value": f"NIM: {nim}%, CoF: {cof}%",
            "component_score": eff_score, "weighted_contribution": round(eff_score * 0.15, 2),
        })

        final_score = round(sum(b["weighted_contribution"] for b in breakdown), 2)
        rating = cls._score_to_rating(final_score)
        industry_risk = cls._detect_industry_risk(company_name, entity_type="nbfc")

        return {
            "final_score": final_score,
            "rating": rating,
            "breakdown": breakdown,
            "industry_risk_level": industry_risk,
            "scoring_model": "NBFC 5-Pillar (IntelliCredit Framework)",
        }

    @classmethod
    def _score_corporate(cls, ratios: list, company_name: str, metrics: dict) -> dict:
        """Original 5-factor Corporate scoring."""
        ratio_dict = {r["name"]: r["value"] for r in ratios}
        breakdown = []

        # ── 1. Leverage (25%) ──
        de = ratio_dict.get("Debt-to-Equity (D/E)")
        if de != "N/A" and de is not None:
            if de < 1:    lev_score = 100
            elif de <= 2: lev_score = 80
            elif de <= 4: lev_score = 60
            else:         lev_score = 30
        else:
            lev_score = 50
        breakdown.append({"factor": "Leverage (D/E)", "weight": 25, "raw_value": de,
                           "component_score": lev_score, "weighted_contribution": round(lev_score * 0.25, 2)})

        # ── 2. Profitability (20%) ──
        ebitda_margin = ratio_dict.get("EBITDA Margin")
        if ebitda_margin != "N/A" and ebitda_margin is not None:
            if ebitda_margin > 20:   prof_score = 100
            elif ebitda_margin >= 10: prof_score = 75
            else:                    prof_score = 40
        else:
            prof_score = 50
        breakdown.append({"factor": "Profitability (EBITDA Margin)", "weight": 20, "raw_value": ebitda_margin,
                           "component_score": prof_score, "weighted_contribution": round(prof_score * 0.20, 2)})

        # ── 3. Liquidity (20%) ──
        cr = ratio_dict.get("Current Ratio")
        if cr != "N/A" and cr is not None:
            if cr > 2:   liq_score = 100
            elif cr >= 1: liq_score = 70
            else:         liq_score = 30
        else:
            liq_score = 50
        breakdown.append({"factor": "Liquidity (Current Ratio)", "weight": 20, "raw_value": cr,
                           "component_score": liq_score, "weighted_contribution": round(liq_score * 0.20, 2)})

        # ── 4. Cash Flow (20%) ──
        dscr = ratio_dict.get("DSCR")
        if dscr != "N/A" and dscr is not None:
            if dscr > 1.5:  cf_score = 100
            elif dscr >= 1: cf_score = 70
            else:           cf_score = 20
        else:
            cf_score = 50
        breakdown.append({"factor": "Cash Flow (DSCR)", "weight": 20, "raw_value": dscr,
                           "component_score": cf_score, "weighted_contribution": round(cf_score * 0.20, 2)})

        # ── 5. Industry Risk (15%) ──
        industry_risk = cls._detect_industry_risk(company_name, entity_type="corporate")
        ind_score = 100 if industry_risk == "LOW" else 65 if industry_risk == "MEDIUM" else 30
        breakdown.append({"factor": "Industry Risk", "weight": 15, "raw_value": industry_risk,
                           "component_score": ind_score, "weighted_contribution": round(ind_score * 0.15, 2)})

        final_score = round(sum(b["weighted_contribution"] for b in breakdown), 2)
        rating = cls._score_to_rating(final_score)
        return {
            "final_score": final_score,
            "rating": rating,
            "breakdown": breakdown,
            "industry_risk_level": industry_risk,
            "scoring_model": "Corporate 5-Factor",
        }

    @classmethod
    def _detect_industry_risk(cls, company_name: str, entity_type: str) -> str:
        """Detect industry risk from company name keywords."""
        name_lower = (company_name or "").lower()

        if entity_type == "NBFC":
            return "MEDIUM"

        for keyword, risk in cls.INDUSTRY_RISK.items():
            if keyword in name_lower:
                return risk

        # Default to medium if unknown
        return "MEDIUM"

    @staticmethod
    def _score_to_rating(score: float) -> str:
        if score >= 90:
            return "AAA"
        elif score >= 80:
            return "AA"
        elif score >= 70:
            return "A"
        elif score >= 60:
            return "BBB"
        elif score >= 50:
            return "BB"
        else:
            return "High Risk"

    # ═══════════════════════════════════════════════════════════════
    #  STEP 5 - ANOMALY / FLAG DETECTION
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def detect_anomalies(ratios: list, inputs: dict, entity_type: str) -> list:
        """
        Automatically flag risk conditions based on computed ratios
        and extracted inputs. Returns a list of triggered flags.
        """
        flags = []
        ratio_dict = {r["name"]: r["value"] for r in ratios}

        # 1. D/E > 10
        de = ratio_dict.get("Debt-to-Equity (D/E)")
        if de != "N/A" and de is not None and de > 10:
            flags.append({
                "flag": "⚠️ High Leverage Risk",
                "condition": f"D/E = {de} (threshold: > 10)",
                "explanation": "Extremely high leverage ratio indicates the company is "
                               "heavily debt-funded with minimal equity buffer.",
            })

        # 2. ICR < 1.5
        icr = ratio_dict.get("Interest Coverage Ratio (ICR)")
        if icr != "N/A" and icr is not None and icr < 1.5:
            flags.append({
                "flag": "⚠️ Debt Servicing Risk",
                "condition": f"ICR = {icr} (threshold: < 1.5)",
                "explanation": "Interest Coverage Ratio below 1.5 indicates the company's "
                               "earnings may not comfortably cover interest obligations.",
            })

        # 3. Current Ratio < 1
        cr = ratio_dict.get("Current Ratio")
        if cr != "N/A" and cr is not None and cr < 1:
            flags.append({
                "flag": "⚠️ Liquidity Stress",
                "condition": f"Current Ratio = {cr} (threshold: < 1)",
                "explanation": "Current liabilities exceed current assets, indicating "
                               "potential short-term liquidity problems.",
            })

        # 4. DSCR < 1
        dscr = ratio_dict.get("DSCR")
        if dscr != "N/A" and dscr is not None and dscr < 1:
            flags.append({
                "flag": "⚠️ Insufficient Cash Flow for Debt Repayment",
                "condition": f"DSCR = {dscr} (threshold: < 1)",
                "explanation": "Operating cash flow is insufficient to cover total "
                               "debt service obligations.",
            })

        # 5. PAT negative (check current period)
        pat = inputs["common"].get("net_profit_pat")
        if pat != "Not Available" and pat is not None and pat < 0:
            flags.append({
                "flag": "⚠️ Profitability Deterioration",
                "condition": f"PAT = {pat} Cr (negative)",
                "explanation": "The company is reporting a net loss, indicating "
                               "profitability concerns.",
            })

        # NBFC-specific flags
        if entity_type == "NBFC":
            # 6. Gross NPA > 5%
            gnpa = inputs["nbfc"].get("gnpa_pct")
            if gnpa != "Not Available" and gnpa is not None and gnpa > 5:
                flags.append({
                    "flag": "⚠️ Asset Quality Concern",
                    "condition": f"Gross NPA = {gnpa}% (threshold: > 5%)",
                    "explanation": "Gross NPA above 5% signals deteriorating asset "
                                   "quality and potential credit losses.",
                })

            # 7. CAR < 15%
            car = inputs["nbfc"].get("car_pct")
            if car != "Not Available" and car is not None and car < 15:
                flags.append({
                    "flag": "⚠️ Capital Adequacy Below Threshold",
                    "condition": f"CAR = {car}% (threshold: < 15%)",
                    "explanation": "Capital Adequacy Ratio below 15% indicates "
                                   "insufficient capital buffer against risk-weighted assets.",
                })

        return flags

    # ═══════════════════════════════════════════════════════════════
    #  ORCHESTRATOR - RUN FULL ANALYSIS
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def run_full_analysis(cls, financial_metrics: dict) -> dict:
        """
        Run the complete 5-step credit analysis pipeline.

        Args:
            financial_metrics: Raw financial metrics dict (from AI extraction
                               or sample data).

        Returns:
            Structured CAM-ready analysis result.
        """
        # Step 1: Classify entity
        classification = cls.classify_entity(financial_metrics)
        entity_type = classification["entity_type"]

        # Step 2: Extract structured inputs
        inputs = cls.extract_inputs(financial_metrics)

        # Step 3: Compute ratios
        ratios = cls.compute_ratios(inputs, entity_type)

        # Step 4: Compute weighted credit score
        company_name = financial_metrics.get("company_name", "")
        scoring = cls.compute_credit_score(ratios, entity_type, company_name, metrics=financial_metrics)

        # Step 5: Detect anomalies
        anomalies = cls.detect_anomalies(ratios, inputs, entity_type)

        return {
            "entity_classification": classification,
            "metadata": financial_metrics.get("metadata", {}),
            "financial_inputs": inputs,
            "credit_ratios": ratios,
            "credit_scoring": scoring,
            "anomaly_flags": anomalies,
            "company_name": company_name,
            "financial_year": financial_metrics.get("financial_year", "N/A"),
        }


# ═══════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def _get_value(metrics: dict, key: str):
    """Safely extract a numeric value from the metrics dict,
    handling both flat values and nested {'value': ...} dicts."""
    val = metrics.get(key)
    if val is None:
        return None
    if isinstance(val, dict):
        return val.get("value")
    return val
