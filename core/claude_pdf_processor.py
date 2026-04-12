"""
Claude PDF Processor - Native Document Understanding
=====================================================
Uses Anthropic Claude's native PDF processing to extract financial
metrics directly from PDF documents without pre-processing.
Falls back to existing regex-based extraction if unavailable.
"""

import base64
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Lazy-init the Anthropic client."""
    global _client
    if _client is None:
        try:
            import anthropic
            from config import Config
            api_key = Config.ANTHROPIC_API_KEY
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY not set - Claude PDF processing unavailable.")
                return None
            _client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            logger.warning("anthropic package not installed - Claude PDF processing unavailable.")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            return None
    return _client


# ═══════════════════════════════════════════════════════════════════
#  KEY PAGE EXTRACTION FOR LARGE PDFs
# ═══════════════════════════════════════════════════════════════════

# Financial section keywords used to score page relevance
FINANCIAL_PAGE_KEYWORDS = [
    "balance sheet", "profit and loss", "statement of profit",
    "cash flow statement", "notes to accounts", "significant accounting",
    "total revenue", "total income", "total expenses", "net worth",
    "total assets", "total liabilities", "shareholders equity",
    "borrowings", "ebitda", "interest expense", "depreciation",
    "current assets", "current liabilities", "short term",
    "long term", "deferred tax", "capital adequacy", "net npa",
    "gnpa", "loan book", "aum", "net interest income",
    "return on assets", "return on equity",
]

MAX_KEY_PAGES = 30  # Max pages to send to Claude
MAX_CLAUDE_SIZE_MB = 32  # Claude's PDF size limit


def _extract_key_pages(filepath: str, max_pages: int = MAX_KEY_PAGES):
    """
    For large PDFs (200-500 pages), score every page by financial keyword
    density and return a new in-memory PDF containing the top N most
    relevant pages. Returns (pdf_bytes, page_numbers, total_pages).
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(filepath)
        total_pages = len(doc)

        # Score each page
        page_scores = []
        for i, page in enumerate(doc):
            text = page.get_text("text").lower()
            score = sum(text.count(kw) for kw in FINANCIAL_PAGE_KEYWORDS)
            page_scores.append((score, i))

        # Sort by score descending, take top N, keep original order
        top_pages = sorted(
            sorted(page_scores, key=lambda x: x[0], reverse=True)[:max_pages],
            key=lambda x: x[1]  # Restore original page order
        )
        selected_indices = [idx for _, idx in top_pages]

        # Build a new mini-PDF from selected pages
        mini_doc = fitz.open()
        mini_doc.insert_pdf(doc, from_page=selected_indices[0],
                            to_page=selected_indices[0])
        # Insert remaining selected pages
        for page_idx in selected_indices[1:]:
            mini_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)

        pdf_bytes = mini_doc.tobytes()
        mini_doc.close()
        doc.close()

        logger.info(
            f"Smart extraction: selected {len(selected_indices)}/{total_pages} "
            f"key financial pages from {os.path.basename(filepath)}"
        )
        return pdf_bytes, selected_indices, total_pages

    except Exception as e:
        logger.error(f"Key page extraction failed: {e}")
        return None, [], 0


# ═══════════════════════════════════════════════════════════════════
#  EXTRACTION PROMPT
# ═══════════════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """You are an expert Indian corporate credit analyst. Analyze this financial document (PDF) and extract ALL key financial metrics from the CONSOLIDATED financial statements.

CRITICAL EXTRACTION RULES (follow these EXACTLY):

1. UNIT DETECTION: Check the header of each financial statement for "Rs. in crore" or "in Lakhs".
   - If "in crore" or "Rs. in crore" -> values are already in Crores, divisor = 1
   - If "in Lakhs" or "in lakh" -> divide all values by 100 to convert to Crores

2. PAT (Profit After Tax): Extract ONLY from the Consolidated Statement of Profit and Loss.
   - Look for "Profit for the year attributable to: Owners of the company" (may be on two lines)
   - This is the PAT figure. Do NOT use total "Profit for the year" which includes non-controlling interest.
   - Do NOT extract PAT from the Auditor's Report, Board's Report, or any narrative text.
   - PAT margin = PAT / Total Income * 100

3. NET WORTH: Extract from the Consolidated Balance Sheet ONLY.
   - PREFERRED: Use "Equity attributable to owners of the Company" (excludes non-controlling interest)
   - FALLBACK: If the preferred line is not found, use "Total equity" instead (better than returning null)
   - Do NOT compute it as shares * face value
   - Typical structure: Equity share capital + Shares pending + Instruments + Other equity = Equity attributable to owners
   - IMPORTANT: You MUST return a numeric value for net_worth. Never return null if equity data exists in the balance sheet.

4. TOTAL DEBT: Sum EXACTLY these THREE Balance Sheet line items:
   - "Debt securities" (NCDs, bonds)
   - "Borrowings (other than debt securities)" - this is typically the LARGEST component
   - "Subordinated liabilities"
   - Total Debt = Sum of above three. Do NOT use partial figures from Board's Report text.
   - Do NOT include lease liabilities.

5. REVENUE & REVENUE GROWTH: Use the Consolidated P&L "Total Income (I+II)" line.
   - revenue_growth_pct = ((current_year_total_income - prior_year_total_income) / prior_year_total_income) * 100
   - Calculate this from the two columns in the P&L. Do NOT extract growth % from narrative text.

6. ENTITY TYPE: Classify as "nbfc" if the company has NII, NPA, CRAR, loan book, or AUM metrics.
   - For NBFCs: Set ebitda to null (not applicable), set current_ratio to null, set dscr to null, set interest_coverage_ratio to null
   - For NBFCs: Compute PPOP (Pre-Provision Operating Profit) = Total Income - Finance Costs - Employee Expense - Other Expenses - Depreciation

7. EBITDA: For NBFCs/banks, set to null (not meaningful). For manufacturing/services companies, extract normally.

Return a JSON object with these fields. Use INR Crores for all monetary values. If a metric is not found or not applicable, set it to null.

{
    "company_name": "...",
    "financial_year": "...",
    "entity_type": "nbfc|manufacturing|services|other",
    "revenue": {"value": 0, "unit": "Cr", "growth_pct": 0},
    "ebitda": {"value": null, "unit": "Cr", "margin_pct": null, "reason": "N/A for NBFC"},
    "ppop": {"value": 0, "unit": "Cr"},
    "ebit": {"value": 0, "unit": "Cr"},
    "pat": {"value": 0, "unit": "Cr", "margin_pct": 0, "growth_pct": 0},
    "total_debt": {"value": 0, "unit": "Cr"},
    "net_worth": {"value": 0, "unit": "Cr"},
    "current_assets": {"value": 0, "unit": "Cr"},
    "current_liabilities": {"value": 0, "unit": "Cr"},
    "interest_expense": {"value": 0, "unit": "Cr"},
    "cash_flow_from_operations": {"value": 0, "unit": "Cr"},
    "nii": {"value": 0, "unit": "Cr", "margin_pct": 0},
    "loan_book": {"value": 0, "unit": "Cr"},
    "gnpa_pct": 0,
    "nnpa_pct": 0,
    "car_pct": 0,
    "cost_of_funds_pct": 0,
    "roa_pct": 0,
    "roe_pct": 0,
    "nim_pct": 0,
    "debt_equity_ratio": 0,
    "current_ratio": 0,
    "interest_coverage_ratio": 0,
    "dscr": 0,
    "total_assets": {"value": 0, "unit": "Cr"},
    "tangible_net_worth": {"value": 0, "unit": "Cr"},
    "working_capital": {"value": 0, "unit": "Cr"},
    "promoter_holding_pct": 0,
    "key_risks": ["..."],
    "key_strengths": ["..."],
    "red_flags": ["..."],
    "data_source": "claude_pdf_extraction"
}

SANITY CHECKS before returning:
- PAT must be less than Revenue
- PAT margin should typically be 5-30% for financial companies
- Total Debt for large NBFCs should be > 100,000 Cr (check you are summing all 3 components)
- Net Worth should EXCLUDE non-controlling interest
- D/E ratio for NBFCs is typically 4-8x
- Revenue growth should be calculated, not extracted from text
- This document may be an extract of key financial pages from a larger report.
- Return ONLY the JSON object, no other text."""


def extract_from_pdf(filepath: str) -> Optional[dict]:
    """
    Extract financial metrics from a PDF using Claude's native
    document understanding.

    Args:
        filepath: Path to the PDF file.

    Returns:
        dict of extracted financial metrics, or None if Claude is unavailable.
    """
    client = _get_client()
    if client is None:
        return None

    if not os.path.exists(filepath):
        logger.error(f"PDF file not found: {filepath}")
        return None

    file_size = os.path.getsize(filepath) / (1024 * 1024)

    try:
        if file_size > MAX_CLAUDE_SIZE_MB:
            # Large PDF (e.g. 200-500 page annual reports): extract key financial pages
            logger.info(
                f"Large PDF ({file_size:.1f} MB) detected. "
                f"Extracting top {MAX_KEY_PAGES} financial pages intelligently..."
            )
            pdf_bytes, selected_pages, total_pages = _extract_key_pages(filepath, MAX_KEY_PAGES)
            if pdf_bytes is None:
                logger.error("Smart page extraction failed, skipping Claude processing.")
                return None
            mini_size = len(pdf_bytes) / (1024 * 1024)
            if mini_size > MAX_CLAUDE_SIZE_MB:
                logger.warning(
                    f"Even key-page extract is {mini_size:.1f} MB > {MAX_CLAUDE_SIZE_MB} MB. "
                    f"Reducing to {MAX_KEY_PAGES // 2} pages..."
                )
                pdf_bytes, selected_pages, total_pages = _extract_key_pages(filepath, MAX_KEY_PAGES // 2)
                if pdf_bytes is None:
                    return None
            pdf_data = base64.standard_b64encode(pdf_bytes).decode("utf-8")
            logger.info(
                f"Smart extract ready: {len(selected_pages)} pages from {total_pages}-page PDF, "
                f"{len(pdf_bytes)/(1024*1024):.1f} MB"
            )
        else:
            # Small/medium PDF: send directly
            with open(filepath, "rb") as f:
                pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

        from config import Config
        model = getattr(Config, "ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        # Send to Claude with document block
        message = client.messages.create(
            model=model,
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": EXTRACTION_PROMPT,
                        },
                    ],
                }
            ],
        )

        # Parse response
        response_text = message.content[0].text

        # Try to extract JSON from the response
        # Handle cases where Claude wraps JSON in markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())
        result["data_source"] = "claude_pdf_extraction"
        logger.info(f"Claude PDF extraction successful for: {filepath}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Claude PDF extraction failed: {e}")
        return None


def is_available() -> bool:
    """Check if Claude PDF processing is available."""
    return _get_client() is not None
