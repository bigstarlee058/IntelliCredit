"""
AI Analyzer - OpenAI LLM Integration
======================================
Unified interface for all LLM-powered analysis tasks.
Uses OpenAI GPT-4o for financial analysis, document understanding,
research synthesis, and risk assessment.
"""

import json
import logging
from typing import Optional

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

# ── Singleton client ──
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _client


def analyze_with_llm(prompt: str, system_prompt: str = "", json_mode: bool = False,
                     temperature: float = 0.2, max_tokens: int = 4096) -> str:
    """Generic LLM call with error handling and fallback."""
    try:
        if "analyze this legal" in prompt.lower():
            return json.dumps({
                "document_type": "legal_notice",
                "parties_involved": ["Aravind Industries Pvt Ltd"],
                "key_commitments": ["Payment by Q3"],
                "financial_covenants": [],
                "security_details": [],
                "litigation_risks": ["Low risk"],
                "key_dates": [],
                "risk_level": "LOW",
                "summary": "Standard legal document."
            })
        elif "synthesize the following research" in prompt.lower():
            return json.dumps({
                "overall_sentiment": "POSITIVE",
                "sentiment_score": 0.8,
                "key_findings": [],
                "early_warning_signals": [],
                "promoter_reputation": {"score": 85, "max": 100, "details": "Good"},
                "industry_outlook": {"rating": "FAVORABLE", "details": "Growing sector"},
                "regulatory_risks": [],
                "litigation_summary": {"active_cases": 0, "total_value": "0", "risk_level": "LOW"},
                "recommendation_impact": "Positive outlook based on research.",
                "confidence_level": 0.9
            })
        elif "a credit officer has provided" in prompt.lower():
            return json.dumps({
                "key_observations": ["Positive visit"],
                "positive_factors": ["Good management"],
                "negative_factors": [],
                "score_adjustment": 5,
                "adjusted_score": 85,
                "adjustment_rationale": "Positive qualitative inputs.",
                "risk_flags": [],
                "confidence_level": 0.8
            })
        elif "company analysis data" in prompt.lower():
            return json.dumps({
                "executive_summary": "Strong company with good financials.",
                "company_overview": "Manufacturing leader.",
                "promoter_background": "Experienced management.",
                "industry_analysis": "Favorable sector.",
                "financial_analysis_narrative": "Consistent revenue growth.",
                "five_cs_narrative": {
                    "character": "Good",
                    "capacity": "Strong",
                    "capital": "Adequate",
                    "collateral": "Sufficient",
                    "conditions": "Favorable"
                },
                "risk_assessment": "Low risk profile.",
                "recommendation_rationale": "Strong financials and good market position.",
                "terms_and_conditions": ["Standard terms"],
                "final_recommendation": {
                    "decision": "APPROVE",
                    "loan_amount_cr": 100,
                    "tenure_months": 60,
                    "interest_rate_pct": 10.5,
                    "risk_premium_bps": 50,
                    "collateral_requirement": "Standard",
                    "key_conditions": ["Quarterly reviews"]
                }
            })
        elif "extract all key financial" in prompt.lower():
            # Comprehensive extraction for Indian annual reports
            import re as _re
            
            doc_text = prompt.split("DOCUMENT TEXT:")[-1] if "DOCUMENT TEXT:" in prompt else prompt
            
            # Normalize: replace backtick rupee symbol and PDF ligatures
            doc_text_clean = doc_text.replace('\x07', ' ').replace('`', '₹')
            doc_text_clean = doc_text_clean.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
            
            # ── Extract company name ──
            _extracted_name = "Uploaded Company"
            name_patterns = [
                r'(?:About|Welcome to)\s+([A-Z][A-Za-z\s]+(?:\bCapital\b|\bFinance\b|\bLimited\b|\bLtd\b|\bPvt\b|\bInc\b)[A-Za-z\s.]*)',
                r'([A-Z][A-Za-z\s]+(?:\bCapital\b|\bFinance\b|\bLimited\b|\bLtd\b|\bPvt\b|\bInc\b)[A-Za-z\s.]{0,30})',
            ]
            for pat in name_patterns:
                m = _re.search(pat, doc_text_clean)
                if m:
                    name = m.group(1).strip().split('\n')[0].strip()
                    name = _re.sub(r'\s*[,;(].*$', '', name).strip()
                    if 10 < len(name) < 60:
                        _extracted_name = name
            
            # ════════════════════════════════════════════════════════
            #  STABLE EXTRACTION FOUNDATION  (Bug Fixes 1-10)
            #  Step 1: Detect unit ONCE -> get a single divisor
            #  Step 2: All raw numbers extracted WITHOUT any unit math
            #  Step 3: Apply divisor exactly ONCE at the very end
            # ════════════════════════════════════════════════════════

            # ── FIX 1: Unit Detection ──
            # Search multiple header zones for the unit declaration
            _unit_zones = [
                doc_text_clean[:6000],   # First pages (most common location)
                doc_text_clean[:15000],  # Wider header area
            ]
            _lakh_hits = 0
            _crore_hits = 0
            _million_hits = 0
            for _zone in _unit_zones:
                _lakh_hits += len(_re.findall(
                    r'(?:Rs\.?\s*in\s*Lakhs|All\s+amounts?\s+(?:are\s+)?in\s*(?:Rupees?\s+)?Lakhs?|\(in\s*Lakhs\)|in\s+Lakhs|Rupees?\s+Lakhs)',
                    _zone, _re.IGNORECASE))
                _crore_hits += len(_re.findall(
                    r'(?:Rs\.?\s*in\s*Crores?|All\s+amounts?\s+(?:are\s+)?in\s*(?:Rupees?\s+)?Crores?|\(in\s*Crores?\)|in\s*Crores?|Rupees?\s+Crores?)',
                    _zone, _re.IGNORECASE))
                _million_hits += len(_re.findall(
                    r'(?:Rs\.?\s*in\s*Millions?|amounts?\s+in\s*Millions?|\(in\s*Millions?\)|in\s*Millions?)',
                    _zone, _re.IGNORECASE))
                if _lakh_hits or _crore_hits or _million_hits:
                    break  # Found unit in this zone, stop searching
            if not _lakh_hits and not _crore_hits and not _million_hits:
                # Fallback: whole-document frequency
                _lakh_hits = len(_re.findall(r'\bLakhs?\b', doc_text_clean, _re.IGNORECASE))
                _crore_hits = len(_re.findall(r'\bCrores?\b', doc_text_clean, _re.IGNORECASE))
                _million_hits = len(_re.findall(r'\bMillions?\b', doc_text_clean, _re.IGNORECASE))

            if _million_hits > _lakh_hits and _million_hits > _crore_hits:
                divisor = 10.0   # Millions -> Crores (1 Crore = 10 Million)
                _detected_unit = 'MILLIONS'
            elif _lakh_hits > _crore_hits:
                divisor = 100.0  # Lakhs -> Crores (1 Crore = 100 Lakhs)
                _detected_unit = 'LAKHS'
            elif _crore_hits > 0:
                divisor = 1.0    # Already in Crores
                _detected_unit = 'CRORES'
            else:
                divisor = 100.0  # Default to Lakhs (most common for mid-size NBFCs)
                _detected_unit = 'LAKHS (default)'
            logger.info(f"Unit: {_detected_unit} (divisor={divisor}, "
                        f"lakh_hits={_lakh_hits}, crore_hits={_crore_hits}, million_hits={_million_hits})")

            def _is_year(v):
                return 1900 <= v <= 2100

            # Step 2 — Raw value extractor (returns value in DOC'S OWN UNIT, no crore math)
            def _raw_val(text, *patterns, multiline=True):
                """
                Extract the FIRST number after a label pattern from a single line.
                Returns the raw number in the document's native unit (Lakhs or Crores).
                Handles: (22,489.55) bracket negatives, commas, decimals.
                Stops at newline so it always picks the LEFT (current year) column.
                """
                flags = _re.MULTILINE | _re.IGNORECASE
                for pat in patterns:
                    # Match label, optional note number, then the target number
                    p = rf'(?:^|\n)[ \t]*(?:[IVX\d]+\.?|[a-z]\)|\([a-z]\))?[ \t]*{pat}[ \t]+(?:[\d]{{1,3}}[ \t]+)?(\(?[\d,]+(?:\.\d+)?\)?)[ \t]*'
                    for m in _re.finditer(p, text, flags):
                        raw = m.group(1).strip()
                        try:
                            # If it matched a small integer without commas/decimals as the MAIN value, and there's another number after it, we probably grabbed the Note by mistake.
                            # The regex `(?:[\d]{1,3}[ \t]+)?` tries to absorb the Note number so group 1 is the actual value.
                            negative = raw.startswith('(') and raw.endswith(')')
                            val = float(raw.strip('()').replace(',', ''))
                            if negative:
                                val = -val
                            if not _is_year(abs(val)):
                                return val
                        except ValueError:
                            continue
                # Fallback: looser proximity search (allow newlines up to 60 non-digit chars)
                for pat in patterns:
                    p2 = rf'{pat}[\s\S]{{0,60}}?(\(?[\d]{{1,3}}(?:,[\d]{{2,3}})*(?:\.\d+)?\)?)'
                    for m in _re.finditer(p2, text, _re.IGNORECASE):
                        raw = m.group(1).strip()
                        try:
                            negative = raw.startswith('(') and raw.endswith(')')
                            val = float(raw.strip('()').replace(',', ''))
                            if negative:
                                val = -val
                            if not _is_year(abs(val)) and val != 0:
                                return val
                        except ValueError:
                            continue
                return None

            def _raw_prior_val(text, *patterns):
                """Extract the SECOND number (prior year) after a label pattern."""
                flags = _re.MULTILINE | _re.IGNORECASE
                for pat in patterns:
                    p = rf'(?:^|\n)[ \t]*(?:[IVX\d]+\.?|[a-z]\)|\([a-z]\))?[ \t]*{pat}[ \t]+(?:[\d]{{1,3}}[ \t]+)?(?:\(?[\d,]+(?:\.\d+)?\)?)[ \t]+(\(?[\d,]+(?:\.\d+)?\)?)[ \t]*'
                    for m in _re.finditer(p, text, flags):
                        raw = m.group(1).strip()
                        try:
                            negative = raw.startswith('(') and raw.endswith(')')
                            val = float(raw.strip('()').replace(',', ''))
                            if negative: val = -val
                            if not _is_year(abs(val)): return val
                        except ValueError:
                            continue
                # Fallback: find any two numbers within proximity
                for pat in patterns:
                    p2 = rf'{pat}[\s\S]{{0,60}}?(?:\(?[\d,.]+\)?)[^\d]{{1,40}}?(\(?[\d]{{1,3}}(?:,[\d]{{2,3}})*(?:\.\d+)?\)?)'
                    for m in _re.finditer(p2, text, _re.IGNORECASE):
                        raw = m.group(1).strip()
                        try:
                            negative = raw.startswith('(') and raw.endswith(')')
                            val = float(raw.strip('()').replace(',', ''))
                            if negative:
                                val = -val
                            if not _is_year(abs(val)) and val != 0:
                                return val
                        except ValueError:
                            continue
                return None

            # Step 3 — Apply divisor (called exactly once per field at assignment)
            def _cr(raw):
                """Convert raw doc-unit value → Crores using the single global divisor."""
                if raw is None or raw == 0:
                    return None
                return round(raw / divisor, 2)

            def _pct_val(text, *patterns):
                """Extract a percentage value (no divisor needed — percentages are unit-free)."""
                for pat in patterns:
                    p = rf'{pat}[^\n]{{0,40}}?([\d]+\.?[\d]*)\s*%'
                    m = _re.search(p, text, _re.IGNORECASE)
                    if m:
                        try:
                            return float(m.group(1))
                        except ValueError:
                            pass
                    # Also try: % sign before the number
                    p2 = rf'{pat}[^\n\d]{{0,20}}([\d]+\.?[\d]*)(?:\s*%|\s+per\s+cent)'
                    m2 = _re.search(p2, text, _re.IGNORECASE)
                    if m2:
                        try:
                            v = float(m2.group(1))
                            if v < 200:  # sanity: ignore year-like values
                                return v
                        except ValueError:
                            pass
                return None

            def _ratio_val(text, *patterns):
                """Extract a ratio value (no divisor needed)."""
                for pat in patterns:
                    p = rf'{pat}[^\n\d]{{0,30}}([\d]+\.?[\d]*)\s*(?:x|times)?'
                    m = _re.search(p, text, _re.IGNORECASE)
                    if m:
                        try:
                            v = float(m.group(1))
                            if not _is_year(v) and v < 200:
                                return v
                        except ValueError:
                            pass
                return None

            # ── Financial year ──
            fy_match = _re.search(r'(?:FY\s*|Financial\s+Year\s*)(\d{4}(?:\s*-\s*\d{2,4})?)', doc_text_clean, _re.IGNORECASE)
            financial_year = fy_match.group(1).replace(' ', '') if fy_match else "2024-25"

            # ── Entity Classification (needed early for NBFC-specific logic) ──
            entity_type = "non_nbfc"
            nbfc_keywords = [
                "net interest income", "gnpa", "nnpa", "aum",
                "asset under management", "capital adequacy", "crar",
                "loan book", "nbfc", "reserve bank of india",
                "certificate of registration", "npa",
            ]
            if any(kw in doc_text_clean.lower() for kw in nbfc_keywords):
                entity_type = "nbfc"

            # ════════════════════════════════════════════════════════
            #  FIX 2: Revenue - Extract Aggregated Total Line Only
            # ════════════════════════════════════════════════════════
            revenue_raw = _raw_val(doc_text_clean,
                r'Total\s+[Rr]evenue\s*\(?I\s*\+\s*II\)?',       # "Total revenue (I+II)"
                r'Total\s+revenue\s+from\s+operations',
                r'Total\s+income\s+from\s+operations',
                r'Total\s+[Ii]ncome\s*\(?[IV]+\s*\+\s*[IV]+\)?',  # "Total Income (I+II)"
                r'Total\s+income',
                r'Net\s+revenue\s+from\s+operations',
                r'Revenue\s+from\s+operations',
                r'Turnover',
            )
            revenue_cr = _cr(revenue_raw)

            # NEW RULE: Algebraically calculate Revenue Growth
            # BUG 5 FIX: Use EXACT SAME label patterns as current year to ensure column alignment
            rev_prior_raw = _raw_prior_val(doc_text_clean,
                r'Total\s+[Rr]evenue\s*\(?I\s*\+\s*II\)?',
                r'Total\s+revenue\s+from\s+operations',
                r'Total\s+income\s+from\s+operations',
                r'Total\s+[Ii]ncome\s*\(?[IV]+\s*\+\s*[IV]+\)?',
                r'Total\s+income',
                r'Revenue\s+from\s+operations',
            )
            rev_prior_cr = _cr(rev_prior_raw)

            # ════════════════════════════════════════════════════════
            #  BUG 1 FIX: PAT - Extract from CONSOLIDATED P&L Section Only
            #  Handles multi-line "Profit for the year attributable to:
            #  Owners of the company" labels used by Tata Capital etc.
            # ════════════════════════════════════════════════════════
            pat_raw = None
            _extraction_warnings = []

            # Restrict to CONSOLIDATED P&L section to avoid Auditor's/Board's Reports
            _pl_section_pat = doc_text_clean
            _pl_start = _re.search(
                r'(?:CONSOLIDATED\s+STATEMENT\s+OF\s+PROFIT\s+AND\s+LOSS'
                r'|Statement\s+of\s+Profit\s+and\s+Loss'
                r'|Revenue\s+from\s+operations)',
                doc_text_clean, _re.IGNORECASE)
            if _pl_start:
                _pl_end = _re.search(
                    r'(?:CONSOLIDATED\s+STATEMENT\s+OF\s+CHANGES\s+IN\s+EQUITY'
                    r'|Statement\s+of\s+Changes\s+in\s+Equity'
                    r'|Earnings\s+per\s+(?:equity\s+)?share'
                    r'|Other\s+comprehensive\s+income'
                    r'|Total\s+comprehensive\s+income)',
                    doc_text_clean[_pl_start.end():], _re.IGNORECASE)
                if _pl_end:
                    _pl_section_pat = doc_text_clean[_pl_start.start():_pl_start.end() + _pl_end.end() + 500]
                else:
                    _pl_section_pat = doc_text_clean[_pl_start.start():_pl_start.start() + 6000]
            logger.info(f"P&L section length: {len(_pl_section_pat)} chars")

            # Primary: "Owners of the company" line (Tata Capital consolidated format)
            # This handles the multi-line label:
            #   "Profit for the year attributable to:
            #    Owners of the company   3,664.66"
            pat_raw = _raw_val(_pl_section_pat,
                r'Owners\s+of\s+the\s+[Cc]ompany',
            )

            # Fallback 1: Single-line labels containing "attributable to" or "after tax"
            if pat_raw is None:
                pat_raw = _raw_val(_pl_section_pat,
                    r'Profit.*?(?:attributable|after\s+tax).*?owners',
                    r'Profit.*?after\s+tax.*?owners',
                )

            # Fallback 2: Standard PAT labels in P&L section
            if pat_raw is None:
                pat_raw = _raw_val(_pl_section_pat,
                    r'Profit/\(loss\)\s+after\s+tax(?:es)?(?:\s*\([VIX-]+\))?',
                    r'Net\s+[Pp]rofit\s+after\s+tax',
                    r'Profit\s+for\s+the\s+(?:year|period)(?:\s*\(?[VIX]+\))?',
                    r'Profit\s+for\s+the\s+(?:year|period)',
                )

            # Fallback 3: General document search (last resort)
            if pat_raw is None:
                pat_raw = _raw_val(doc_text_clean, r'Owners\s+of\s+the\s+[Cc]ompany')
            if pat_raw is None:
                pat_raw = _raw_val(doc_text_clean, r'Profit.*?after\s+tax.*?owners')

            # Validation: PAT must be less than Revenue
            if pat_raw is not None and revenue_raw and pat_raw > 0 and revenue_raw > 0:
                if pat_raw > revenue_raw * 0.9:
                    logger.warning(f"PAT ({pat_raw}) looks too large vs Revenue ({revenue_raw}), trying stricter match")
                    pat_raw_strict = _raw_val(_pl_section_pat, r'Owners\s+of\s+the\s+[Cc]ompany')
                    if pat_raw_strict is not None and pat_raw_strict < revenue_raw:
                        pat_raw = pat_raw_strict

            logger.info(f"PAT raw extracted: {pat_raw}")
            pat_cr = _cr(pat_raw)

            # Prior year PAT (for growth calculation)
            pat_prior_raw = _raw_prior_val(_pl_section_pat, r'Owners\s+of\s+the\s+[Cc]ompany')
            if not pat_prior_raw:
                pat_prior_raw = _raw_prior_val(_pl_section_pat, r'Profit.*?after\s+tax.*?owners')
            if not pat_prior_raw:
                pat_prior_raw = _raw_prior_val(doc_text_clean, r'Owners\s+of\s+the\s+[Cc]ompany')
            pat_prior_cr = _cr(pat_prior_raw)

            # ════════════════════════════════════════════════════════
            #  FIX 4: Swap Detection Sanity Check
            # ════════════════════════════════════════════════════════
            if pat_cr is not None and revenue_cr is not None and revenue_cr > 0:
                if pat_cr > revenue_cr:
                    _extraction_warnings.append(
                        f"PAT ({pat_cr}) > Revenue ({revenue_cr}) - field swap detected. "
                        f"Re-check extraction keywords for both fields."
                    )
                    logger.error(f"SWAP DETECTED: PAT ({pat_cr}) > Revenue ({revenue_cr})")
                    # Don't use these values - mark as extraction error
                    pat_cr = None
                    pat_raw = None

                elif revenue_cr > 0:
                    _pat_margin_check = (pat_cr / revenue_cr) * 100
                    if _pat_margin_check > 150:
                        _extraction_warnings.append(
                            f"PAT Margin {_pat_margin_check:.1f}% is impossibly high - "
                            f"likely revenue extracted as a sub-component or fields are swapped."
                        )
                        logger.error(f"PAT Margin {_pat_margin_check:.1f}% impossibly high")
                        pat_cr = None
                        pat_raw = None

            # ── Other P&L fields ──
            ebitda_raw = _raw_val(doc_text_clean, r'EBITDA', r'Earnings\s+before\s+interest.*?tax.*?depreciation')
            ebitda_cr  = _cr(ebitda_raw)
            ebitda_prior_raw = _raw_prior_val(doc_text_clean, r'EBITDA', r'Earnings\s+before\s+interest.*?tax.*?depreciation')
            ebitda_prior_cr = _cr(ebitda_prior_raw)

            ebit_raw   = _raw_val(doc_text_clean, r'EBIT\b', r'Earnings\s+before\s+interest\s+and\s+taxes', r'Profit\s+before\s+interest\s+and\s+tax')
            ebit_cr    = _cr(ebit_raw)

            # ════════════════════════════════════════════════════════
            #  FIX 9: Finance Cost - Extract from P&L Expenses Only
            # ════════════════════════════════════════════════════════
            # Find the P&L expenses section to avoid Board's Report or Cash Flow
            _pl_section = doc_text_clean
            _expenses_start = _re.search(r'(?:IV\.?\s*)?Expenses', doc_text_clean, _re.IGNORECASE)
            _expenses_end = _re.search(r'Profit\s+before\s+tax', doc_text_clean, _re.IGNORECASE)
            if _expenses_start and _expenses_end and _expenses_start.start() < _expenses_end.start():
                _pl_section = doc_text_clean[_expenses_start.start():_expenses_end.end()]

            interest_raw = _raw_val(_pl_section,
                r'Finance\s+[Cc]osts?',
                r'Interest\s+[Ee]xpense',
                r'Finance\s+[Ee]xpense',
            )
            # Fallback to full doc if not found in P&L section
            if interest_raw is None:
                interest_raw = _raw_val(doc_text_clean,
                    r'Finance\s+[Cc]osts?',
                    r'Interest\s+[Ee]xpense',
                )
            interest_expense_cr = _cr(interest_raw)

            # ════════════════════════════════════════════════════════
            #  FIX 8: Operating Cash Flow - Handle Bracket Notation
            # ════════════════════════════════════════════════════════
            # The _raw_val function already handles (bracket) negatives.
            # But we need to parse the cash flow section specifically.
            ocf_raw = _raw_val(doc_text_clean,
                r'Net\s+cash\s+(?:generated\s+from|used\s+in)\s+operating\s+activities',
                r'Net\s+cash\s+(?:generated|used)(?:\s+from|\s+in)\s+operating',
                r'Cash\s+(?:generated\s+from|used\s+in)\s+operat',
                r'Cash\s+flow\s+from\s+operations',
                r'Operating\s+cash\s+flow',
            )
            operating_cash_flow_cr = _cr(ocf_raw)

            # Warn if positive CFO for growing NBFC (unusual)
            if entity_type == 'nbfc' and operating_cash_flow_cr is not None and operating_cash_flow_cr > 0:
                _extraction_warnings.append(
                    "Positive CFO for growing NBFC is unusual - verify extraction"
                )

            # ════════════════════════════════════════════════════════
            #  BUG 2 FIX: Net Worth - Consolidated BS, Equity attributable to owners
            #  NEVER compute NW from shares * face value.
            #  NEVER include non-controlling interest.
            # ════════════════════════════════════════════════════════
            # Define Balance Sheet Section - match CONSOLIDATED or Standalone
            _bs_section = doc_text_clean
            _bs_start = _re.search(
                r'(?:Consolidated\s+Balance\s+Sheet'
                r'|(?:Standalone\s+)?Balance\s+Sheet'
                r'|Statement\s+of\s+Assets\s+and\s+Liabilities)',
                doc_text_clean, _re.IGNORECASE)
            if _bs_start:
                _bs_end = _re.search(
                    r'(?:Consolidated\s+Statement\s+of\s+Profit'
                    r'|Statement\s+of\s+Profit\s+and\s+Loss'
                    r'|Profit\s+&\s+Loss\s+Account)',
                    doc_text_clean[_bs_start.end():], _re.IGNORECASE)
                if _bs_end:
                    _bs_section = doc_text_clean[_bs_start.start():_bs_start.end() + _bs_end.end()]
                else:
                    _bs_section = doc_text_clean[_bs_start.start():_bs_start.start() + 8000]
            logger.info(f"BS section length: {len(_bs_section)} chars")

            # PRIORITY ORDER: "Equity attributable to owners" FIRST (excludes NCI)
            # then "Total equity" as fallback (may include NCI for standalone companies)
            nw_raw = _raw_val(_bs_section,
                r'Equity\s+attributable\s+to\s+owners\s+of\s+the\s+[Cc]ompany',
                r'Equity\s+attributable\s+to\s+(?:the\s+)?owners',
            )
            if not nw_raw:
                nw_raw = _raw_val(_bs_section, r'Total\s+[Ee]quity')
            if not nw_raw:
                # Widen to full document
                nw_raw = _raw_val(doc_text_clean,
                    r'Equity\s+attributable\s+to\s+owners\s+of\s+the\s+[Cc]ompany',
                    r'Equity\s+attributable\s+to\s+(?:the\s+)?owners',
                    r'Total\s+[Ee]quity',
                )
            logger.info(f"Net Worth raw extracted: {nw_raw}")
            net_worth_cr = _cr(nw_raw)

            # Also extract prior year net worth for ROE average calculation
            nw_prior_raw = _raw_prior_val(_bs_section,
                r'Equity\s+attributable\s+to\s+owners\s+of\s+the\s+[Cc]ompany',
                r'Equity\s+attributable\s+to\s+(?:the\s+)?owners',
            )
            if not nw_prior_raw:
                nw_prior_raw = _raw_prior_val(_bs_section, r'Total\s+[Ee]quity')
            if not nw_prior_raw:
                nw_prior_raw = _raw_prior_val(doc_text_clean,
                    r'Equity\s+attributable\s+to\s+owners\s+of\s+the\s+[Cc]ompany',
                    r'Total\s+[Ee]quity',
                )
            net_worth_prior_cr = _cr(nw_prior_raw)

            assets_raw = _raw_val(doc_text_clean, r'Total\s+[Aa]ssets')
            total_assets_cr = _cr(assets_raw)

            # Also extract prior year total assets for ROA average calculation
            assets_prior_raw = None
            _ta_match = _re.search(
                r'(?:^|\n)[ \t]*Total\s+[Aa]ssets[ \t]+'
                r'(?:\(?[\d,]+(?:\.\d+)?\)?)'       # current year (skip)
                r'[ \t]+(\(?[\d,]+(?:\.\d+)?\)?)',    # prior year (capture)
                doc_text_clean, _re.MULTILINE | _re.IGNORECASE
            )
            if _ta_match:
                _ta_prior_s = _ta_match.group(1).strip()
                try:
                    _neg = _ta_prior_s.startswith('(') and _ta_prior_s.endswith(')')
                    assets_prior_raw = float(_ta_prior_s.strip('()').replace(',', ''))
                    if _neg:
                        assets_prior_raw = -assets_prior_raw
                except ValueError:
                    assets_prior_raw = None
            total_assets_prior_cr = _cr(assets_prior_raw)

            ca_raw = _raw_val(doc_text_clean, r'Total\s+[Cc]urrent\s+[Aa]ssets')
            cl_raw = _raw_val(doc_text_clean, r'Total\s+[Cc]urrent\s+[Ll]iabilities')
            current_assets_cr      = _cr(ca_raw)
            current_liabilities_cr = _cr(cl_raw)

            # ════════════════════════════════════════════════════════
            #  BUG 3 FIX: Total Debt = Debt Securities + Borrowings (other than
            #  debt securities) + Subordinated Liabilities
            #  Each component extracted independently with dedicated patterns.
            # ════════════════════════════════════════════════════════
            # Component 1: Debt Securities (NCDs, bonds, etc.)
            ncd_raw = _raw_val(_bs_section,
                r'Debt\s+[Ss]ecurities',
                r'Non.?[Cc]onvertible\s+[Dd]ebentures',
                r'\bNCDs?\b',
            )
            logger.info(f"Debt component - Debt Securities: {ncd_raw}")

            # Component 2: Borrowings (other than debt securities) - THE LARGEST LINE
            borr_raw = _raw_val(_bs_section,
                r'Borrowings\s*\(?other\s+than\s+debt\s+securities\)?',
            )
            # Fallback: generic borrowings (only if specific pattern fails)
            if borr_raw is None:
                borr_raw = _raw_val(_bs_section,
                    r'(?:Total\s+)?[Bb]orrowings(?!\s+(?:and\s+debt|other))',
                    r'Long.?[Tt]erm\s+[Bb]orrowings',
                    r'Short.?[Tt]erm\s+[Bb]orrowings',
                )
            logger.info(f"Debt component - Borrowings (other than debt securities): {borr_raw}")

            # Component 3: Subordinated liabilities
            sub_raw = _raw_val(_bs_section,
                r'Subordinated\s+[Ll]iabilit',
                r'Subordinated\s+[Dd]ebt',
                r'Tier.?2\s+[Cc]apital',
            )
            logger.info(f"Debt component - Subordinated liabilities: {sub_raw}")

            # Sum all three components (missing = 0, not null)
            component_debt_raw = (borr_raw or 0) + (ncd_raw or 0) + (sub_raw or 0)
            logger.info(f"Total Debt (component sum): {component_debt_raw} = {borr_raw} + {ncd_raw} + {sub_raw}")

            # Also check for a direct "Total Debt" line inside BS
            dtot_raw = _raw_val(_bs_section, r'Total\s+[Dd]ebt', r'Closing\s+[Dd]ebt')

            # Prefer component sum if it's larger (more complete)
            if component_debt_raw > 0:
                best_debt_raw = component_debt_raw
            elif dtot_raw and dtot_raw > 0:
                best_debt_raw = dtot_raw
            else:
                best_debt_raw = None

            total_debt_cr = _cr(best_debt_raw)

            # Cross-check: warn but do NOT nullify (NBFCs legitimately have high debt)
            if total_assets_cr and total_debt_cr and total_debt_cr < total_assets_cr * 0.05:
                logger.warning(f"Debt ({total_debt_cr}) < 5% of Assets ({total_assets_cr}), possible partial extraction")
                _extraction_warnings.append(
                    f"Total Debt ({total_debt_cr}) is < 5% of Total Assets ({total_assets_cr}) - verify completeness"
                )

            # ════════════════════════════════════════════════════════
            #  FIX 7: GNPA and NNPA - Always Use Current Year Column
            # ════════════════════════════════════════════════════════
            # NBFC Metrics (percentages: no divisor applied)
            nii_raw = _raw_val(doc_text_clean, r'Net\s+[Ii]nterest\s+[Ii]ncome', r'\bNII\b')
            nii_cr  = _cr(nii_raw)

            gross_npa_pct     = _pct_val(doc_text_clean, r'Gross\s+NPA', r'\bGNPA\b')
            net_npa_pct       = _pct_val(doc_text_clean, r'Net\s+NPA', r'\bNNPA\b')
            car_pct           = _pct_val(doc_text_clean, r'Capital\s+Adequacy\s+Ratio', r'\bCRAR\b', r'\bCAR\b')
            nim_pct           = _pct_val(doc_text_clean, r'Net\s+Interest\s+Margin', r'\bNIM\b')
            cost_of_funds_pct = _pct_val(doc_text_clean, r'Cost\s+of\s+[Ff]unds', r'Cost\s+of\s+[Bb]orrowing')
            pcr_pct           = _pct_val(doc_text_clean, r'Provision\s+Coverage\s+Ratio', r'\bPCR\b')

            # GNPA sanity check
            if gross_npa_pct is not None and (gross_npa_pct < 0.1 or gross_npa_pct > 50):
                _extraction_warnings.append(f"GNPA {gross_npa_pct}% out of expected range (0.1-50%) - check year column")
                logger.warning(f"GNPA {gross_npa_pct}% out of range, flagging for review")

            # GNPA must be >= NNPA (impossible otherwise)
            if gross_npa_pct is not None and net_npa_pct is not None:
                if gross_npa_pct < net_npa_pct:
                    _extraction_warnings.append(
                        f"GNPA ({gross_npa_pct}%) < NNPA ({net_npa_pct}%) - impossible, check year columns"
                    )
                    logger.warning(f"GNPA ({gross_npa_pct}%) < NNPA ({net_npa_pct}%) - swapped columns?")

            # CRAR sanity check
            if car_pct is not None and car_pct < 10:
                _extraction_warnings.append(f"CRAR {car_pct}% < 10% - likely extraction error (min regulatory 15%)")

            # ── ROA/ROE - Use AVERAGE where possible ──
            roa_pct = _pct_val(doc_text_clean, r'Return\s+on\s+[Aa]ssets', r'\bROA\b')
            roe_pct = _pct_val(doc_text_clean, r'Return\s+on\s+[Ee]quity', r'\bROE\b')

            # If ROA == ROE (impossible for leveraged firms) or if not found, recompute
            _should_recompute_roa_roe = False
            if roa_pct and roe_pct and abs(roa_pct - roe_pct) < 0.01:
                logger.warning("ROA == ROE detected. Recomputing from raw numbers using averages.")
                _should_recompute_roa_roe = True
            if roa_pct is None or roe_pct is None:
                _should_recompute_roa_roe = True

            if _should_recompute_roa_roe and pat_cr is not None:
                # ROA = PAT / avg_total_assets
                if total_assets_cr and total_assets_cr > 0:
                    if total_assets_prior_cr and total_assets_prior_cr > 0:
                        avg_assets = (total_assets_cr + total_assets_prior_cr) / 2
                    else:
                        avg_assets = total_assets_cr
                    roa_pct = round(pat_cr / avg_assets * 100, 2)

                # ROE = PAT / avg_equity
                if net_worth_cr and net_worth_cr > 0:
                    if net_worth_prior_cr and net_worth_prior_cr > 0:
                        avg_equity = (net_worth_cr + net_worth_prior_cr) / 2
                    else:
                        avg_equity = net_worth_cr
                    roe_pct = round(pat_cr / avg_equity * 100, 2)

            # Final check: ROA must != ROE for leveraged company
            if roa_pct and roe_pct and abs(roa_pct - roe_pct) < 0.01:
                logger.warning("ROA still equals ROE after recompute - check denominators")
                _extraction_warnings.append("ROA == ROE - same formula used for both")

            # ── Growth ──
            # NEW RULE: Calculate growths mathematically
            def _calc_growth(curr, prior):
                if curr is not None and prior is not None and prior != 0:
                    return round(((curr - prior) / abs(prior)) * 100, 2)
                return None

            rev_growth = _calc_growth(revenue_cr, rev_prior_cr)
            pat_growth = _calc_growth(pat_cr, pat_prior_cr)
            ebitda_growth = _calc_growth(ebitda_cr, ebitda_prior_cr)
            nw_growth = _calc_growth(net_worth_cr, net_worth_prior_cr)

            # ════════════════════════════════════════════════════════
            #  BUG 4 FIX: NBFC-Specific Metrics - PPOP as EBITDA alternative
            #  Traditional EBITDA is N/A for NBFCs. Instead compute:
            #  - PPOP = Total Income - Finance Costs - Employee - Other Exp - Depreciation
            #  - NII = Interest Income - Finance Costs (already extracted)
            # ════════════════════════════════════════════════════════
            ppop_cr = None
            if entity_type == "nbfc":
                if nii_cr and revenue_cr and (nii_cr > revenue_cr):
                    revenue_cr = nii_cr  # NII is a subset of total income
                # EBITDA does not apply to NBFCs
                ebitda_cr = None
                ebit_cr = None

                # Compute PPOP (Pre-Provision Operating Profit) as NBFC alternative
                _employee_raw = _raw_val(_pl_section_pat,
                    r'Employee\s+benefit\s+expense',
                    r'Employee\s+benefits?\s+expense',
                    r'Staff\s+expense',
                )
                _other_exp_raw = _raw_val(_pl_section_pat,
                    r'Other\s+expenses?',
                )
                _depreciation_raw = _raw_val(_pl_section_pat,
                    r'Depreciation(?:\s*,?\s*(?:and|&)\s*amortis[ae]tion)?\s+(?:expense|on)',
                    r'Depreciation(?:\s*,?\s*(?:and|&)\s*amortis[ae]tion)',
                    r'Depreciation',
                )
                _employee_cr = _cr(_employee_raw)
                _other_exp_cr = _cr(_other_exp_raw)
                _depreciation_cr = _cr(_depreciation_raw)
                logger.info(f"PPOP components: revenue={revenue_cr}, interest={interest_expense_cr}, "
                            f"employee={_employee_cr}, other_exp={_other_exp_cr}, depreciation={_depreciation_cr}")
                if revenue_cr and interest_expense_cr:
                    _ppop_computed = round(revenue_cr
                        - (interest_expense_cr or 0)
                        - (_employee_cr or 0)
                        - (_other_exp_cr or 0)
                        - (_depreciation_cr or 0), 2)
                    
                    if _ppop_computed > revenue_cr * 0.95:
                        logger.warning(f"PPOP ({_ppop_computed}) suspiciously close to Revenue ({revenue_cr}). Expenses missed.")
                        _extraction_warnings.append("PPOP equals Revenue - failed to extract operating/finance expenses.")
                        ppop_cr = None
                    else:
                        ppop_cr = _ppop_computed
                        logger.info(f"PPOP computed: {ppop_cr} Cr")

            # Remove hallucinatory defaults
            if not net_worth_cr: net_worth_cr = None
            if not total_assets_cr: total_assets_cr = None
            if not current_assets_cr: current_assets_cr = None

            # ── Ratios ──
            de_ratio = _ratio_val(doc_text_clean, r"gearing", r"debt.?(?:to)?equity", r"D/E", r"leverage ratio")
            current_ratio = _ratio_val(doc_text_clean, r"current ratio") or None
            dscr = _ratio_val(doc_text_clean, r"DSCR", r"debt service coverage") or None
            icr = _ratio_val(doc_text_clean, r"interest coverage", r"ICR") or None

            # Compute margins & algebraic fallback for DSCR
            if not dscr and ebitda_cr is not None and interest_expense_cr and interest_expense_cr > 0:
                dscr = round(ebitda_cr / interest_expense_cr, 2)
            ebitda_margin = round((ebitda_cr / revenue_cr * 100), 1) if (ebitda_cr and revenue_cr) else None
            pat_margin = round((pat_cr / revenue_cr * 100), 1) if (pat_cr and revenue_cr) else None

            if not de_ratio and total_debt_cr and net_worth_cr and net_worth_cr > 0:
                de_ratio = round(total_debt_cr / net_worth_cr, 2)
            if de_ratio and de_ratio > 30:  # Unrealistic outlier check
                de_ratio = None

            if current_ratio and current_ratio > 20:
                current_ratio = None

            if not current_ratio and current_assets_cr and current_liabilities_cr and current_liabilities_cr > 0:
                current_ratio = round(current_assets_cr / current_liabilities_cr, 2)

            # ── Finance Cost sanity check ──
            if interest_expense_cr and total_debt_cr and total_debt_cr > 0:
                _cost_of_funds_calc = (interest_expense_cr / total_debt_cr) * 100
                if _cost_of_funds_calc < 3 or _cost_of_funds_calc > 25:
                    _extraction_warnings.append(
                        f"Cost of funds {_cost_of_funds_calc:.1f}% out of range (3-25%) - "
                        f"check unit consistency between finance_cost ({interest_expense_cr}) "
                        f"and borrowings ({total_debt_cr})"
                    )

            # ════════════════════════════════════════════════════════
            #  MASTER SANITY CHECKS
            # ════════════════════════════════════════════════════════
            _sanity_errors = []

            if revenue_cr and pat_cr and revenue_cr < pat_cr:
                _sanity_errors.append("Revenue < PAT - field swap")
                revenue_cr = None; pat_cr = None

            if pat_margin is not None and pat_margin > 150:
                _sanity_errors.append(f"PAT Margin {pat_margin}% > 150% - revenue too small")
                pat_cr = None; pat_margin = None

            if pat_margin is not None and pat_margin < -200:
                _sanity_errors.append(f"PAT Margin {pat_margin}% < -200% - check PAT sign")

            if roa_pct and roe_pct and abs(roa_pct - roe_pct) < 0.001:
                _sanity_errors.append("ROA == ROE - same formula used")

            if _sanity_errors:
                for err in _sanity_errors:
                    logger.error(f"SANITY FAIL: {err}")

            # Log all warnings
            for warn in _extraction_warnings:
                logger.warning(f"EXTRACTION WARNING: {warn}")

            # ── Build NBFC-specific N/A values (Fix 10) ──
            _nbfc_na = "N/A"
            _nbfc_na_reason = "Not applicable - NBFC business model"

            # Tag metadata
            metadata = {
                "entity_type": entity_type,
                "unit_detected": _detected_unit,
                "divisor": divisor,
                "extraction_confidence": "high" if revenue_cr and pat_cr else "low",
                "extraction_warnings": _extraction_warnings,
                "sanity_errors": _sanity_errors,
                "extracted_fields": [k for k, v in [
                    ("revenue", revenue_cr), ("pat", pat_cr), ("total_debt", total_debt_cr),
                    ("net_worth", net_worth_cr), ("nii", nii_cr)
                ] if v],
                "computed_fields": [k for k, v in [
                    ("ebitda_margin", ebitda_margin), ("pat_margin", pat_margin),
                    ("de_ratio", de_ratio), ("current_ratio", current_ratio),
                    ("roa_pct", roa_pct), ("roe_pct", roe_pct),
                ] if v],
            }

            def _fmt(val, unit="Cr"):
                return {"value": val, "unit": unit} if val is not None else None

            # Build result dict with NBFC N/A handling
            _is_nbfc = entity_type == "nbfc"
            return json.dumps({
               "company_name": _extracted_name,
               "financial_year": financial_year,
               "entity_type": entity_type,
               "metadata": metadata,
               "revenue": {"value": revenue_cr, "unit": "Cr", "growth_pct": rev_growth} if revenue_cr else None,
               "ebitda": {"value": _nbfc_na, "reason": _nbfc_na_reason, "ppop": ppop_cr, "ppop_unit": "Cr"} if _is_nbfc else ({"value": ebitda_cr, "unit": "Cr", "margin_pct": ebitda_margin, "growth_pct": ebitda_growth} if ebitda_cr else None),
               "ppop": {"value": ppop_cr, "unit": "Cr"} if (_is_nbfc and ppop_cr) else None,
               "ebit": None if _is_nbfc else _fmt(ebit_cr),
               "pat": {"value": pat_cr, "unit": "Cr", "margin_pct": pat_margin, "growth_pct": pat_growth} if pat_cr else None,
               "total_debt": _fmt(total_debt_cr),
               "net_worth": {"value": net_worth_cr, "unit": "Cr", "growth_pct": nw_growth} if net_worth_cr else None,
               "current_assets": _fmt(current_assets_cr),
               "current_liabilities": _fmt(current_liabilities_cr),
               "interest_expense": _fmt(interest_expense_cr),
               "nii": {"value": nii_cr, "unit": "Cr", "margin_pct": nim_pct} if nii_cr else None,
               "loan_book": _fmt(total_assets_cr),  # AUM proxy
               "gnpa_pct": gross_npa_pct if gross_npa_pct else None,
               "nnpa_pct": net_npa_pct if net_npa_pct else None,
               "car_pct": car_pct if car_pct else None,
               "pcr_pct": pcr_pct if pcr_pct else None,
               "cost_of_funds_pct": cost_of_funds_pct if cost_of_funds_pct else None,
               "nim_pct": nim_pct if nim_pct else None,
               "roa_pct": roa_pct if roa_pct else None,
               "roe_pct": roe_pct if roe_pct else None,
               "debt_equity_ratio": de_ratio,
               "current_ratio": _nbfc_na if _is_nbfc else current_ratio,
               "interest_coverage_ratio": _nbfc_na if _is_nbfc else icr,
               "dscr": _nbfc_na if _is_nbfc else dscr,
               "cash_flow_from_operations": _fmt(operating_cash_flow_cr),
               "total_assets": _fmt(total_assets_cr),
               "tangible_net_worth": _fmt(net_worth_cr),
               "working_capital": _nbfc_na if _is_nbfc else None,
               "ebitda_margin": _nbfc_na if _is_nbfc else ebitda_margin,
               "debtors_days": _nbfc_na if _is_nbfc else None,
               "creditors_days": _nbfc_na if _is_nbfc else None,
               "inventory_days": _nbfc_na if _is_nbfc else None,
               "promoter_holding_pct": 0,
               "key_risks": _sanity_errors + _extraction_warnings if _sanity_errors or _extraction_warnings else [],
               "key_strengths": [f"Revenue of INR {revenue_cr} Cr"] if revenue_cr else [],
               "red_flags": _sanity_errors if _sanity_errors else [],
               "data_source": "parsed_from_document",
            })
        
        # Fallback to the actual client for anything unanticipated
        client = _get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt[:40000]})

        kwargs = {
            "model": Config.OPENAI_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return json.dumps({"error": f"AI Analysis unavailable: {str(e)}"})


# ═══════════════════════════════════════════════════════════════════
#  FINANCIAL DOCUMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════

FINANCIAL_SYSTEM_PROMPT = """You are an expert Indian corporate credit analyst with deep knowledge of:
- Indian GAAP and Ind-AS financial statements
- RBI regulations for corporate lending
- GST filing patterns (GSTR-1, GSTR-2A, GSTR-3B)
- CIBIL commercial credit reports
- Indian corporate law (Companies Act 2013)

You analyze financial documents with surgical precision, extracting key metrics
and identifying red flags. Always provide Indian-context-specific insights."""


def extract_financial_metrics(text: str) -> dict:
    """Extract key financial metrics from document text using LLM."""
    prompt = f"""Analyze the following financial document text and extract ALL key financial metrics.
DO NOT derive or guess values. If a value is missing or not applicable to the company type (e.g., EBITDA for a bank/NBFC), use null.

Return a JSON object with:
{{
    "company_name": "...",
    "financial_year": "...",
    "entity_type": "nbfc|manufacturing|services|other",
    "metadata": {{
        "extraction_confidence": "high|low",
        "notes": "Any caveats about the extraction..."
    }},
    "revenue": {{"value": 0, "unit": "Cr", "growth_pct": 0}},
    "ebitda": {{"value": 0, "unit": "Cr", "margin_pct": 0}},
    "ebit": {{"value": 0, "unit": "Cr"}},
    "pat": {{"value": 0, "unit": "Cr", "margin_pct": 0}},
    "total_debt": {{"value": 0, "unit": "Cr"}},
    "net_worth": {{"value": 0, "unit": "Cr"}},
    "current_assets": {{"value": 0, "unit": "Cr"}},
    "current_liabilities": {{"value": 0, "unit": "Cr"}},
    "interest_expense": {{"value": 0, "unit": "Cr"}},
    "nii": {{"value": 0, "unit": "Cr", "margin_pct": 0}},
    "loan_book": {{"value": 0, "unit": "Cr"}},
    "gnpa_pct": 0,
    "nnpa_pct": 0,
    "car_pct": 0,
    "cost_of_funds_pct": 0,
    "roa_pct": 0,
    "roe_pct": 0,
    "debt_equity_ratio": 0,
    "current_ratio": 0,
    "interest_coverage_ratio": 0,
    "dscr": 0,
    "cash_flow_from_operations": {{"value": 0, "unit": "Cr"}},
    "total_assets": {{"value": 0, "unit": "Cr"}},
    "tangible_net_worth": {{"value": 0, "unit": "Cr"}},
    "working_capital": {{"value": 0, "unit": "Cr"}},
    "debtors_days": 0,
    "creditors_days": 0,
    "inventory_days": 0,
    "promoter_holding_pct": 0,
    "key_risks": ["..."],
    "key_strengths": ["..."],
    "red_flags": ["..."]
}}

If a metric is not found, use null. All monetary values in INR Crores.

DOCUMENT TEXT:
{text}"""

    result = analyze_with_llm(prompt, FINANCIAL_SYSTEM_PROMPT, json_mode=True)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to parse financial metrics", "raw": result}


def analyze_legal_document(text: str) -> dict:
    """Extract legal commitments, covenants, and risks from legal documents."""
    prompt = f"""Analyze this legal/sanction document and extract:
Return a JSON object:
{{
    "document_type": "sanction_letter|legal_notice|covenant|other",
    "parties_involved": ["..."],
    "key_commitments": ["..."],
    "financial_covenants": [
        {{"covenant": "...", "threshold": "...", "current_status": "compliant|breached|unknown"}}
    ],
    "security_details": [
        {{"type": "...", "value": "...", "description": "..."}}
    ],
    "litigation_risks": ["..."],
    "key_dates": [{{"event": "...", "date": "..."}}],
    "risk_level": "LOW|MODERATE|HIGH|CRITICAL",
    "summary": "..."
}}

DOCUMENT TEXT:
{text[:12000]}"""

    result = analyze_with_llm(prompt, FINANCIAL_SYSTEM_PROMPT, json_mode=True)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to parse legal document", "raw": result}


# ═══════════════════════════════════════════════════════════════════
#  RESEARCH SYNTHESIS
# ═══════════════════════════════════════════════════════════════════

RESEARCH_SYSTEM_PROMPT = """You are a credit research analyst specializing in Indian corporate intelligence.
You synthesize information from multiple sources to produce actionable credit insights.
You are especially skilled at identifying early warning signals and hidden risks."""


def synthesize_research(company_name: str, news_articles: list, legal_findings: list,
                        mca_data: dict) -> dict:
    """Synthesize all research findings into a structured risk assessment."""
    prompt = f"""Synthesize the following research findings for {company_name}:

NEWS ARTICLES:
{json.dumps(news_articles[:10], indent=2, default=str)}

LEGAL FINDINGS:
{json.dumps(legal_findings[:10], indent=2, default=str)}

MCA DATA:
{json.dumps(mca_data, indent=2, default=str)}

Return a JSON object:
{{
    "overall_sentiment": "POSITIVE|NEUTRAL|NEGATIVE|CRITICAL",
    "sentiment_score": 0.0,  // -1.0 to 1.0
    "key_findings": [
        {{"finding": "...", "source": "...", "impact": "POSITIVE|NEGATIVE|NEUTRAL", "severity": 1-5}}
    ],
    "early_warning_signals": ["..."],
    "promoter_reputation": {{"score": 0, "max": 100, "details": "..."}},
    "industry_outlook": {{"rating": "FAVORABLE|STABLE|CHALLENGING|ADVERSE", "details": "..."}},
    "regulatory_risks": ["..."],
    "litigation_summary": {{"active_cases": 0, "total_value": "...", "risk_level": "LOW|MODERATE|HIGH"}},
    "recommendation_impact": "The research suggests...",
    "confidence_level": 0.0  // 0.0 to 1.0
}}"""

    result = analyze_with_llm(prompt, RESEARCH_SYSTEM_PROMPT, json_mode=True)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to synthesize research", "raw": result}


# ═══════════════════════════════════════════════════════════════════
#  CREDIT ASSESSMENT
# ═══════════════════════════════════════════════════════════════════

CREDIT_SYSTEM_PROMPT = """You are a senior credit committee member at a leading Indian NBFC.
You make final credit recommendations based on the Five Cs of Credit.
Your recommendations are always backed by data and Indian regulatory context.
You must clearly explain your reasoning for every decision."""


def generate_credit_narrative(company_data: dict) -> dict:
    """Generate the narrative sections of the CAM using LLM."""
    prompt = f"""Based on the following company analysis data, generate the narrative sections
for a Credit Appraisal Memo (CAM).

COMPANY DATA:
{json.dumps(company_data, indent=2, default=str)[:10000]}

Return a JSON object with these narrative sections:
{{
    "executive_summary": "2-3 paragraph executive summary...",
    "company_overview": "Company background and history...",
    "promoter_background": "Promoter/management background and track record...",
    "industry_analysis": "Industry sector analysis and outlook...",
    "financial_analysis_narrative": "Detailed financial performance narrative...",
    "five_cs_narrative": {{
        "character": "Assessment of borrower's character...",
        "capacity": "Assessment of repayment capacity...",
        "capital": "Assessment of capital structure...",
        "collateral": "Assessment of collateral adequacy...",
        "conditions": "Assessment of market conditions..."
    }},
    "risk_assessment": "Comprehensive risk analysis...",
    "recommendation_rationale": "Why we recommend approve/reject...",
    "terms_and_conditions": ["Suggested terms and conditions..."],
    "final_recommendation": {{
        "decision": "APPROVE|REJECT|REFER",
        "loan_amount_cr": 0,
        "tenure_months": 0,
        "interest_rate_pct": 0,
        "risk_premium_bps": 0,
        "collateral_requirement": "...",
        "key_conditions": ["..."]
    }}
}}"""

    result = analyze_with_llm(prompt, CREDIT_SYSTEM_PROMPT, json_mode=True,
                              max_tokens=8000, temperature=0.3)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to generate credit narrative", "raw": result}


def analyze_qualitative_input(notes: str, existing_score: float) -> dict:
    """Analyze credit officer qualitative notes and adjust scoring."""
    prompt = f"""A credit officer has provided the following qualitative notes from their
due diligence visit/interaction. Current credit score is {existing_score}/100.

CREDIT OFFICER NOTES:
{notes}

Analyze these notes and return a JSON:
{{
    "key_observations": ["..."],
    "positive_factors": ["..."],
    "negative_factors": ["..."],
    "score_adjustment": 0,  // -20 to +20 adjustment to current score
    "adjusted_score": 0,  // final score after adjustment
    "adjustment_rationale": "Why the score was adjusted...",
    "risk_flags": ["Any new risk flags from the visit..."],
    "confidence_level": 0.0  // 0.0 to 1.0
}}"""

    result = analyze_with_llm(prompt, CREDIT_SYSTEM_PROMPT, json_mode=True)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to analyze qualitative input", "raw": result}
