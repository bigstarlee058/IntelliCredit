"""
core/ai_analyzer.py  —  IntelliCredit Fixed Pipeline
=====================================================
Key fixes over original:
  1. Unit detection scans ENTIRE document, not just first 15,000 chars
  2. Per-table / per-section unit override on top of global divisor
  3. Fuzzy section fencing: handles "Consolidated", "Standalone", variant spellings
  4. 300-character proximity lookahead (was 60)
  5. Number extraction handles Indian comma groups (1,23,456) + parentheses negatives
  6. Zero-skipping: doesn't return 0.0 as a valid metric (usually formatting noise)
  7. Debt = explicit 3-component sum with per-component reporting
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# (regex_pattern, divisor_to_crores)
UNIT_MAP: List[Tuple[str, float]] = [
    (r"\(rs?\.?\s*in\s*crores?\)",                   1.0),
    (r"\(rs?\.?\s*in\s*lakh[s]?\)",                  0.01),
    (r"\(rs?\.?\s*in\s*lacs?\)",                     0.01),
    (r"\(rs?\.?\s*in\s*millions?\)",                  0.1),
    (r"\(rs?\.?\s*in\s*billions?\)",                100.0),
    (r"\(rs?\.?\s*in\s*thousands?\)",              0.0001),
    (r"all\s+amounts?\s+(?:are\s+)?in\s+(?:rs?\.?\s*)?crores?",    1.0),
    (r"all\s+amounts?\s+(?:are\s+)?in\s+(?:rs?\.?\s*)?lakh[s]?",   0.01),
    (r"all\s+amounts?\s+(?:are\s+)?in\s+(?:rs?\.?\s*)?lacs?",      0.01),
    (r"all\s+amounts?\s+(?:are\s+)?in\s+(?:rs?\.?\s*)?millions?",   0.1),
    (r"figures?\s+are\s+in\s+(?:rs?\.?\s*)?lakh[s]?",              0.01),
    (r"figures?\s+are\s+in\s+(?:rs?\.?\s*)?crores?",               1.0),
    (r"rs?\.\s*in\s*lakh[s]?",                                      0.01),
    (r"rs?\.\s*in\s*crores?",                                        1.0),
    (r"rs?\.\s*in\s*millions?",                                       0.1),
    (r"amounts?\s+in\s+(?:rs?\.?\s*)?lakh[s]?",                    0.01),
    (r"amounts?\s+in\s+(?:rs?\.?\s*)?crores?",                      1.0),
]

# Ordered section-detection patterns (most specific first)
# Each entry: (section_key, [regex_patterns_in_priority_order])
SECTION_PATTERNS: Dict[str, List[str]] = {
    "profit_loss": [
        r"(?:consolidated|standalone)?\s*statement\s+of\s+profit\s+(?:and|&)\s+loss",
        r"profit\s+(?:and|&)\s+loss\s+(?:account|statement)",
        r"(?:consolidated|standalone)?\s*profit\s+(?:and|&)\s+loss",
        r"income\s+(?:and|&)\s+expenditure\s+(?:account|statement)",
        r"statement\s+of\s+income\s+(?:and|&)\s+expenditure",
    ],
    "balance_sheet": [
        r"(?:consolidated|standalone)?\s*balance\s+sheet",
        r"statement\s+of\s+(?:financial\s+position|assets\s+and\s+liabilities)",
        r"(?:consolidated|standalone)?\s*statement\s+of\s+financial\s+position",
    ],
    "cash_flow": [
        r"(?:consolidated|standalone)?\s*(?:statement\s+of\s+)?cash\s+flows?",
        r"cash\s+flow\s+statement",
    ],
    "equity_changes": [
        r"statement\s+of\s+changes?\s+in\s+equity",
        r"changes?\s+in\s+(?:shareholders['']?\s+)?equity",
    ],
    "notes": [
        r"notes?\s+(?:forming\s+part\s+of|to\s+(?:the\s+)?)(?:financial\s+statements?|accounts?)",
        r"schedules?\s+(?:forming\s+part\s+of|to\s+(?:the\s+)?)(?:financial\s+statements?|accounts?)",
    ],
}

# Metric search labels (ordered from most-specific to least-specific)
METRIC_PATTERNS: Dict[str, List[str]] = {
    "pat": [
        r"profit\s+after\s+tax(?:ation)?",
        r"profit\s+for\s+the\s+(?:year|period)",
        r"net\s+profit\s+(?:after\s+tax(?:ation)?)?",
        r"(?:total\s+)?comprehensive\s+income\s+for\s+the\s+(?:year|period)",
        r"profit\s+attributable\s+to\s+(?:owners?|equity\s+holders?|shareholders?)",
        r"\bpat\b",
    ],
    "revenue": [
        r"(?:total\s+)?revenue\s+from\s+operations",
        r"net\s+revenue\s+from\s+operations",
        r"total\s+net\s+interest\s+(?:and\s+related\s+)?income",
        r"net\s+interest\s+income",
        r"total\s+income\s+from\s+operations",
        r"(?:gross\s+)?(?:revenue|turnover|sales)(?:\s+from\s+operations)?",
        r"total\s+income",
        r"interest\s+earned",
    ],
    "ebitda": [
        r"\bebitda\b",
        r"earnings?\s+before\s+interest(?:,?\s+finance\s+costs?)?,\s*tax(?:ation)?,\s*depreciation",
        r"operating\s+profit\s+before\s+depreciation",
        r"\bpbdit\b",
        r"profit\s+before\s+interest\s+and\s+(?:depreciation|amortization)",
    ],
    "net_worth": [
        r"total\s+equity\s+(?:attributable\s+to\s+owners?|shareholders?)?",
        r"equity\s+attributable\s+to\s+(?:owners?|equity\s+holders?|shareholders?)\s+of\s+the\s+(?:parent|company)",
        r"(?:total\s+)?shareholders['']?\s+(?:equity|funds?)",
        r"(?:total\s+)?net\s+(?:worth|assets)",
        r"(?:total\s+)?owners['']?\s+equity",
    ],
    "debt_securities": [
        r"debt\s+securities(?:\s+issued)?",
        r"non.?convertible\s+debentures?\s*\(?\s*ncds?\s*\)?",
        r"bonds?\s+(?:and\s+)?debentures?(?:\s+issued)?",
        r"market\s+borrowings?",
    ],
    "borrowings": [
        r"borrowings?\s+other\s+than\s+debt\s+securities",
        r"(?:other\s+)?borrowings?(?:\s+and\s+credit\s+facilities)?",
        r"(?:short|long).?term\s+borrowings?",
        r"term\s+loans?\s+from\s+banks?",
        r"bank\s+(?:borrowings?|loans?|overdrafts?)",
        r"secured\s+(?:and\s+unsecured\s+)?(?:loans?|borrowings?)",
    ],
    "subordinated": [
        r"subordinated\s+(?:liabilities|debt|bonds?|debentures?)",
        r"tier\s*[- ]?2\s+(?:capital|bonds?|instruments?|debt)",
        r"perpetual\s+(?:debt|bonds?|instruments?)",
    ],
}

# Number pattern handles: 1,23,456.78  |  (1,234.56)  |  plain 12345
_NUMBER_RE = re.compile(r"(\()([\d,]+(?:\.\d+)?)\)|(?<!\w)([\d,]+(?:\.\d+)?)(?!\w)")


# ---------------------------------------------------------------------------
# Main Extractor
# ---------------------------------------------------------------------------

class FinancialMetricsExtractor:
    """
    Extracts financial metrics from raw text of Indian financial documents.

    Usage:
        extractor = FinancialMetricsExtractor()
        metrics   = extractor.extract_all_metrics(full_document_text)
    """

    def __init__(self):
        self._global_divisor: float = 1.0
        self._section_divisors: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_all_metrics(self, full_text: str) -> Dict:
        """
        Master extraction method.
        Returns a dict with metrics, ratios, debt components, and debug info.
        """
        # 1. Global unit — scan ENTIRE document
        self._global_divisor = self._detect_unit(full_text)
        logger.info(f"Global divisor: {self._global_divisor}")

        # 2. Section fencing
        sections = self._fence_sections(full_text)
        logger.info(f"Sections found: {list(sections.keys())}")

        # 3. Per-section unit override
        for sec_name, sec_text in sections.items():
            local = self._detect_unit(sec_text)
            if local != 1.0:
                self._section_divisors[sec_name] = local
                logger.info(f"  Section '{sec_name}' override divisor: {local}")

        # 4. Extract from P&L
        pl_text = sections.get("profit_loss", full_text)
        pl_div  = self._section_divisors.get("profit_loss", self._global_divisor)

        revenue = self._extract_metric(pl_text, "revenue", pl_div)
        pat     = self._extract_metric(pl_text, "pat",     pl_div)
        ebitda  = self._extract_metric(pl_text, "ebitda",  pl_div)

        # 5. Extract from Balance Sheet
        bs_text = sections.get("balance_sheet", full_text)
        bs_div  = self._section_divisors.get("balance_sheet", self._global_divisor)

        net_worth = self._extract_metric(bs_text, "net_worth", bs_div)

        debt_securities = self._extract_metric(bs_text, "debt_securities", bs_div)
        borrowings      = self._extract_metric(bs_text, "borrowings",      bs_div)
        subordinated    = self._extract_metric(bs_text, "subordinated",    bs_div)
        total_debt = self._sum_components(
            [debt_securities, borrowings, subordinated]
        )

        # 6. Derived ratios
        dte  = self._safe_div(total_debt, net_worth)
        dscr = self._estimate_dscr(ebitda, total_debt)

        return {
            "metrics": {
                "revenue_cr":    revenue,
                "pat_cr":        pat,
                "ebitda_cr":     ebitda,
                "net_worth_cr":  net_worth,
                "total_debt_cr": total_debt,
            },
            "debt_components": {
                "debt_securities_cr":        debt_securities,
                "borrowings_cr":             borrowings,
                "subordinated_liabilities_cr": subordinated,
            },
            "ratios": {
                "debt_to_equity":        dte,
                "interest_coverage_dscr": dscr,
            },
            "debug": {
                "global_divisor":  self._global_divisor,
                "section_divisors": self._section_divisors,
                "sections_found": list(sections.keys()),
            },
        }

    # ------------------------------------------------------------------
    # Unit Detection
    # ------------------------------------------------------------------

    def _detect_unit(self, text: str) -> float:
        """
        Searches the ENTIRE text (not just first N chars) for a unit
        declaration and returns the corresponding Crore divisor.
        Falls back to 1.0 (assume Crores) if nothing found.
        """
        text_lower = text.lower()
        for pattern, divisor in UNIT_MAP:
            if re.search(pattern, text_lower):
                logger.debug(f"Unit match: '{pattern}' → divisor={divisor}")
                return divisor
        logger.warning("No unit declaration found. Defaulting to Crores (divisor=1.0).")
        return 1.0

    # ------------------------------------------------------------------
    # Section Fencing
    # ------------------------------------------------------------------

    def _fence_sections(self, text: str) -> Dict[str, str]:
        """
        Identifies section boundaries using fuzzy regex.
        Returns a dict mapping section_key → section_text.
        Falls back to empty dict (caller uses full_text) if nothing found.
        """
        text_lower = text.lower()
        positions: Dict[str, int] = {}

        for sec_key, patterns in SECTION_PATTERNS.items():
            for pat in patterns:
                m = re.search(pat, text_lower)
                if m:
                    positions[sec_key] = m.start()
                    logger.debug(f"Section '{sec_key}' found at char {m.start()} via '{pat}'")
                    break  # First matching pattern wins

        if not positions:
            logger.warning("No sections detected — will use full document for all metrics.")
            return {}

        # Sort sections by their position in the document
        ordered = sorted(positions.items(), key=lambda kv: kv[1])
        sections: Dict[str, str] = {}

        for i, (sec_key, start) in enumerate(ordered):
            end = ordered[i + 1][1] if i + 1 < len(ordered) else len(text)
            sections[sec_key] = text[start:end]

        return sections

    # ------------------------------------------------------------------
    # Metric Extraction
    # ------------------------------------------------------------------

    def _extract_metric(
        self, text: str, metric_name: str, divisor: float
    ) -> Optional[float]:
        """
        Searches text for metric labels, then looks ahead up to 300 chars
        for the first valid number.  Returns value normalized to Crores.
        """
        patterns = METRIC_PATTERNS.get(metric_name, [])
        text_lower = text.lower()

        for pat in patterns:
            for m in re.finditer(pat, text_lower, re.IGNORECASE):
                window = text[m.start(): m.start() + 300]
                value = self._first_number(window)
                if value is not None:
                    converted = value / divisor if divisor else value
                    logger.info(
                        f"[{metric_name}] raw={value}, divisor={divisor}, "
                        f"result={converted:.2f} Cr  (via '{pat}')"
                    )
                    return round(converted, 2)

        logger.warning(f"[{metric_name}] Not found in text of length {len(text)}")
        return None

    def _first_number(self, text: str) -> Optional[float]:
        """
        Extracts the first meaningful number from a text snippet.
        Handles:
            • Indian comma format:  1,23,45,678.90
            • Parentheses negative: (1,234.56) → -1234.56
            • Plain integers and decimals
        Skips: zero values (formatting noise), em-dashes, hyphens.
        """
        for m in _NUMBER_RE.finditer(text):
            is_negative = m.group(1) == "("  # parenthesis open
            raw_num = m.group(2) or m.group(3)
            if raw_num is None:
                continue
            clean = raw_num.replace(",", "")
            try:
                value = float(clean)
            except ValueError:
                continue

            if value == 0.0:
                continue  # skip zero — almost always a placeholder/formatting cell

            return -value if is_negative else value

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sum_components(values: List[Optional[float]]) -> Optional[float]:
        """Sums non-None components; returns None only if ALL are None."""
        valid = [v for v in values if v is not None]
        return round(sum(valid), 2) if valid else None

    @staticmethod
    def _safe_div(
        numerator: Optional[float], denominator: Optional[float]
    ) -> Optional[float]:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return round(numerator / denominator, 2)

    @staticmethod
    def _estimate_dscr(
        ebitda: Optional[float], total_debt: Optional[float]
    ) -> Optional[float]:
        """
        Estimates DSCR = EBITDA / Interest.
        Interest is approximated as 9% of Total Debt (conservative Indian NBFC rate).
        Returns None if either input is missing.
        """
        if ebitda is None or total_debt is None or total_debt == 0:
            return None
        estimated_interest = total_debt * 0.09
        if estimated_interest == 0:
            return None
        return round(ebitda / estimated_interest, 2)


# ---------------------------------------------------------------------------
# Estimation Engine (Bank Statement / GST fallback)
# ---------------------------------------------------------------------------

class DerivedMetricsEngine:
    """
    Estimates financial metrics from raw transactional data when no
    formal financial statement is available.

    Bank Statement mode: uses credit/debit totals.
    GST mode: uses declared taxable value with industry margin proxies.
    """

    # Conservative MSME proxies
    GST_EBITDA_MARGIN = 0.15
    GST_PAT_MARGIN    = 0.10
    BS_EBITDA_PAT_MULTIPLIER = 1.30   # EBITDA ≈ PAT * 1.3
    BS_DEBT_OUTFLOW_RATIO    = 0.15   # Total Debt ≈ 15% of annual outflows

    def from_bank_statement(self, df: "pd.DataFrame") -> Dict:
        """
        df must have at minimum two numeric columns identifiable as
        'credit' and 'debit' amounts.
        Returns estimated metrics dict.
        """
        credit_col, debit_col = self._identify_credit_debit_cols(df)
        if credit_col is None:
            raise ValueError(
                "Could not identify credit/debit columns in bank statement."
            )

        total_credits = df[credit_col].apply(self._to_float).sum()
        total_debits  = df[debit_col].apply(self._to_float).sum()
        net_cashflow  = total_credits - total_debits

        revenue   = total_credits
        pat       = net_cashflow
        ebitda    = pat * self.BS_EBITDA_PAT_MULTIPLIER
        net_worth = None   # cannot estimate from bank statement alone
        total_debt = total_debits * self.BS_DEBT_OUTFLOW_RATIO

        return {
            "source": "bank_statement",
            "is_estimate": True,
            "metrics": {
                "revenue_cr":    round(revenue   / 1e7, 4),  # paise → Cr
                "pat_cr":        round(pat        / 1e7, 4),
                "ebitda_cr":     round(ebitda     / 1e7, 4),
                "net_worth_cr":  net_worth,
                "total_debt_cr": round(total_debt / 1e7, 4),
            },
        }

    def from_gst_filings(self, total_taxable_value_cr: float) -> Dict:
        """
        Derives profitability from GST-declared taxable value using
        conservative MSME industry margin proxies.
        """
        revenue = total_taxable_value_cr
        ebitda  = revenue * self.GST_EBITDA_MARGIN
        pat     = revenue * self.GST_PAT_MARGIN

        return {
            "source": "gst_filing",
            "is_estimate": True,
            "metrics": {
                "revenue_cr":   round(revenue, 2),
                "pat_cr":       round(pat,     2),
                "ebitda_cr":    round(ebitda,  2),
                "net_worth_cr": None,
                "total_debt_cr": None,
            },
            "proxies_used": {
                "ebitda_margin": self.GST_EBITDA_MARGIN,
                "pat_margin":    self.GST_PAT_MARGIN,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _identify_credit_debit_cols(
        self, df: "pd.DataFrame"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Heuristically identifies credit and debit columns by checking
        column names against common Indian bank statement headers.
        """
        credit_keywords = ["credit", "deposit", "cr", "inflow", "received"]
        debit_keywords  = ["debit",  "withdrawal", "dr", "outflow", "paid"]

        credit_col = self._find_col(df.columns, credit_keywords)
        debit_col  = self._find_col(df.columns, debit_keywords)
        return credit_col, debit_col

    @staticmethod
    def _find_col(columns, keywords: List[str]) -> Optional[str]:
        for col in columns:
            if any(kw in col.lower() for kw in keywords):
                return col
        return None

    @staticmethod
    def _to_float(val) -> float:
        if val is None:
            return 0.0
        try:
            return float(str(val).replace(",", "").replace("₹", "").strip() or 0)
        except (ValueError, TypeError):
            return 0.0
