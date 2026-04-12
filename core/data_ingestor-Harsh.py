"""
core/data_ingestor.py  —  IntelliCredit Fixed Pipeline
=======================================================
Key fixes over original:
  1. Borderless table extraction (text-strategy fallback)
  2. Multi-column layout word sorting (prevents interleaved column text)
  3. OCR preprocessing: grayscale + contrast + binarize + high DPI
  4. Encoding chain extended with iso-8859-1
  5. Excel: 70% column-overlap threshold for sheet concatenation
  6. Header detection: picks row with fewest NaN values in first 15 rows
"""

import io
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
import pytesseract
from docx import Document
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF Ingestor
# ---------------------------------------------------------------------------

class PDFIngestor:
    """
    Extracts tables and text from PDFs using a 3-strategy cascade:
        1. pdfplumber  (bordered  tables)
        2. pdfplumber  (borderless / text-aligned tables)
        3. PyMuPDF     (block-sorted text)
        4. pytesseract (OCR with preprocessing, scanned pages only)
    """

    # --- Table extraction settings ---
    _SETTINGS_BORDERED = {
        "vertical_strategy":   "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance":       3,
        "join_tolerance":       3,
        "edge_min_length":     10,
        "min_words_vertical":   3,
        "min_words_horizontal": 1,
    }
    _SETTINGS_BORDERLESS = {
        "vertical_strategy":   "text",
        "horizontal_strategy": "text",
        "snap_tolerance":       5,
        "join_tolerance":       5,
        "edge_min_length":     10,
        "min_words_vertical":   3,
        "min_words_horizontal": 1,
    }
    _SETTINGS_MIXED = {
        "vertical_strategy":   "lines_strict",
        "horizontal_strategy": "text",
        "snap_tolerance":       3,
        "join_tolerance":       3,
        "edge_min_length":     10,
    }

    def extract(self, filepath: str) -> Dict:
        """
        Returns:
            {
                "tables": [ {"page": int, "data": List[List[str]]} ],
                "text":   str,
                "extraction_method": str,
                "errors": List[str]
            }
        """
        result = {
            "tables": [],
            "text": "",
            "extraction_method": None,
            "errors": [],
        }

        try:
            tables, text = self._extract_pdfplumber(filepath)
            result["tables"] = tables
            result["text"] = text
            result["extraction_method"] = "pdfplumber"
            logger.info(f"pdfplumber: {len(tables)} tables, {len(text)} chars")
        except Exception as e:
            result["errors"].append(f"pdfplumber failed: {e}")

        # Supplement with PyMuPDF if text is thin
        if len(result["text"].strip()) < 500:
            try:
                fitz_text = self._extract_pymupdf(filepath)
                if len(fitz_text) > len(result["text"]):
                    result["text"] = fitz_text
                    result["extraction_method"] = "pymupdf"
                    logger.info(f"pymupdf: {len(fitz_text)} chars")
            except Exception as e:
                result["errors"].append(f"PyMuPDF failed: {e}")

        # OCR fallback for scanned PDFs
        if len(result["text"].strip()) < 200:
            try:
                ocr_text = self._extract_ocr(filepath)
                result["text"] = ocr_text
                result["extraction_method"] = "ocr"
                logger.info(f"OCR: {len(ocr_text)} chars")
            except Exception as e:
                result["errors"].append(f"OCR failed: {e}")

        return result

    # ------------------------------------------------------------------
    # Strategy 1 & 2: pdfplumber  (bordered → borderless → mixed)
    # ------------------------------------------------------------------

    def _extract_pdfplumber(self, filepath: str) -> Tuple[List[Dict], str]:
        all_tables: List[Dict] = []
        all_text_parts: List[str] = []

        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):

                # --- Table extraction ---
                tables = page.extract_tables(self._SETTINGS_BORDERED)
                if not tables or all(not t for t in tables):
                    tables = page.extract_tables(self._SETTINGS_BORDERLESS)
                if not tables or all(not t for t in tables):
                    tables = page.extract_tables(self._SETTINGS_MIXED)

                for table in (tables or []):
                    if table and len(table) > 1:
                        cleaned = [
                            [str(cell).strip() if cell is not None else "" for cell in row]
                            for row in table
                        ]
                        all_tables.append({"page": page_num, "data": cleaned})

                # --- Text extraction with column-aware word sorting ---
                words = page.extract_words(
                    x_tolerance=3,
                    y_tolerance=3,
                    keep_blank_chars=False,
                    use_text_flow=False,   # <-- do NOT use PDF reading order
                    extra_attrs=["fontname", "size"],
                )

                if words:
                    page_text = self._words_to_lines(words)
                else:
                    page_text = page.extract_text(layout=True) or ""

                all_text_parts.append(f"--- PAGE {page_num} ---\n{page_text}")

        return all_tables, "\n\n".join(all_text_parts)

    def _words_to_lines(self, words: List[Dict]) -> str:
        """
        Groups words by vertical position (5-pt buckets) then sorts each
        line left-to-right.  Handles multi-column layouts where the PDF
        reading order would otherwise interleave two columns.
        """
        if not words:
            return ""

        # Bucket words into lines by rounding 'top' to nearest 5 pts
        lines_dict: Dict[int, List[Dict]] = {}
        for w in words:
            bucket = round(w["top"] / 5) * 5
            lines_dict.setdefault(bucket, []).append(w)

        # Sort buckets top-to-bottom, words left-to-right within each bucket
        result_lines: List[str] = []
        for bucket_top in sorted(lines_dict.keys()):
            line_words = sorted(lines_dict[bucket_top], key=lambda w: w["x0"])
            result_lines.append(" ".join(w["text"] for w in line_words))

        return "\n".join(result_lines)

    # ------------------------------------------------------------------
    # Strategy 3: PyMuPDF
    # ------------------------------------------------------------------

    def _extract_pymupdf(self, filepath: str) -> str:
        doc = fitz.open(filepath)
        parts: List[str] = []

        for page_num, page in enumerate(doc, start=1):
            # "blocks" mode preserves spatial order better than raw text
            blocks = page.get_text("blocks", sort=True)
            page_text = "\n".join(
                b[4].strip() for b in blocks if b[4].strip()
            )
            parts.append(f"--- PAGE {page_num} ---\n{page_text}")

        doc.close()
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Strategy 4: OCR with preprocessing
    # ------------------------------------------------------------------

    def _extract_ocr(self, filepath: str) -> str:
        """
        OCR pipeline:
            1. Render at 3× zoom (~216 DPI) for sharpness
            2. Convert to grayscale
            3. Boost contrast
            4. Binarize (threshold at 140)
            5. pytesseract with PSM 6 (uniform block of text)
        """
        doc = fitz.open(filepath)
        parts: List[str] = []

        for page_num, page in enumerate(doc, start=1):
            # High-res render
            mat = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # Grayscale
            img = img.convert("L")

            # Contrast boost
            img = ImageEnhance.Contrast(img).enhance(2.0)

            # Binarize
            img = img.point(lambda px: 0 if px < 140 else 255, "1")

            custom_cfg = r"--oem 3 --psm 6 -l eng"
            page_text = pytesseract.image_to_string(img, config=custom_cfg)
            parts.append(f"--- PAGE {page_num} ---\n{page_text}")

        doc.close()
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Structured Data Ingestor (CSV / Excel)
# ---------------------------------------------------------------------------

class StructuredDataIngestor:
    """
    Reads CSV and Excel files with:
        • Encoding safety chain for Indian bank exports
        • Intelligent header detection (scan first 15 rows for fewest NaN)
        • Multi-sheet auto-concatenation with 70% column-overlap threshold
    """

    ENCODING_CHAIN = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def extract_csv(self, filepath: str) -> pd.DataFrame:
        last_error = None
        for enc in self.ENCODING_CHAIN:
            try:
                df = pd.read_csv(
                    filepath,
                    encoding=enc,
                    on_bad_lines="skip",
                    header=None,
                    dtype=str,
                )
                df = self._fix_header(df)
                logger.info(f"CSV read with encoding={enc}, shape={df.shape}")
                return df
            except (UnicodeDecodeError, pd.errors.ParserError) as e:
                last_error = e
                continue

        raise ValueError(
            f"Could not read CSV '{filepath}' with any encoding. "
            f"Last error: {last_error}"
        )

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------

    def extract_excel(self, filepath: str) -> pd.DataFrame:
        try:
            all_sheets: Dict[str, pd.DataFrame] = pd.read_excel(
                filepath, sheet_name=None, header=None, dtype=str
            )
        except Exception as e:
            raise ValueError(f"Failed to open Excel '{filepath}': {e}")

        # Filter out empty / mostly-blank sheets
        valid: Dict[str, pd.DataFrame] = {}
        for name, df in all_sheets.items():
            if df is None or df.empty or df.shape[0] < 2:
                continue
            density = df.notna().sum().sum() / max(df.shape[0] * df.shape[1], 1)
            if density < 0.10:
                logger.debug(f"Skipping sparse sheet: '{name}' (density={density:.2%})")
                continue
            valid[name] = self._fix_header(df)

        if not valid:
            raise ValueError(f"No valid sheets in '{filepath}'")

        logger.info(f"Valid sheets: {list(valid.keys())}")

        # Group sheets with identical column structures and concatenate
        groups = self._group_compatible_sheets(valid)
        if groups:
            # Use the group with the most total rows
            best_group = max(
                groups, key=lambda g: sum(valid[n].shape[0] for n in g)
            )
            logger.info(f"Concatenating sheets: {best_group}")
            return pd.concat(
                [valid[n] for n in best_group], ignore_index=True
            )

        # Fall back to largest single sheet
        return max(valid.values(), key=lambda d: d.shape[0])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fix_header(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Scans the first 15 rows and promotes the row with the most non-null
        cells as the column header, discarding title/blank rows above it.
        """
        scan = min(15, len(df))
        best_row, best_count = 0, -1

        for i in range(scan):
            count = int(df.iloc[i].notna().sum())
            if count > best_count:
                best_count = count
                best_row = i

        df.columns = df.iloc[best_row].astype(str).str.strip()
        df = df.iloc[best_row + 1:].reset_index(drop=True)
        return df

    def _group_compatible_sheets(
        self, sheets: Dict[str, pd.DataFrame]
    ) -> List[List[str]]:
        """
        Returns groups of sheet names whose column sets overlap ≥ 70%.
        """
        names = list(sheets.keys())
        used: set = set()
        groups: List[List[str]] = []

        for i, n1 in enumerate(names):
            if n1 in used:
                continue
            cols1 = set(sheets[n1].columns.str.lower().str.strip())
            group = [n1]

            for n2 in names[i + 1:]:
                if n2 in used:
                    continue
                cols2 = set(sheets[n2].columns.str.lower().str.strip())
                union = cols1 | cols2
                if not union:
                    continue
                overlap = len(cols1 & cols2) / len(union)
                if overlap >= 0.70:
                    group.append(n2)
                    used.add(n2)

            if len(group) > 1:
                groups.append(group)
                used.add(n1)

        return groups


# ---------------------------------------------------------------------------
# DOCX Ingestor
# ---------------------------------------------------------------------------

class DocxIngestor:
    """Extracts all paragraphs and tables from a Word document."""

    def extract(self, filepath: str) -> str:
        doc = Document(filepath)
        parts: List[str] = []

        for block in doc.element.body:
            tag = block.tag.split("}")[-1]  # strip namespace

            if tag == "p":
                text = "".join(r.text for r in block.iterchildren() if hasattr(r, "text") and r.text)
                if text.strip():
                    parts.append(text.strip())

            elif tag == "tbl":
                # Flatten table rows into pipe-delimited strings
                for row in block.iterchildren():
                    cells = []
                    for cell in row.iterchildren():
                        cell_text = "".join(
                            n.text or "" for n in cell.iter() if hasattr(n, "text")
                        ).strip()
                        cells.append(cell_text)
                    if any(cells):
                        parts.append(" | ".join(cells))

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Unified Router
# ---------------------------------------------------------------------------

class DataIngestor:
    """
    Routes a file to the correct ingestor based on extension.
    Usage:
        ingestor = DataIngestor()
        result   = ingestor.ingest("/path/to/file.pdf")
    """

    def __init__(self):
        self._pdf   = PDFIngestor()
        self._data  = StructuredDataIngestor()
        self._docx  = DocxIngestor()

    def ingest(self, filepath: str) -> Dict:
        ext = Path(filepath).suffix.lower()

        if ext == ".pdf":
            return self._pdf.extract(filepath)

        elif ext == ".csv":
            df = self._data.extract_csv(filepath)
            return {"dataframe": df, "text": df.to_string(index=False)}

        elif ext in (".xlsx", ".xls", ".xlsm"):
            df = self._data.extract_excel(filepath)
            return {"dataframe": df, "text": df.to_string(index=False)}

        elif ext in (".docx", ".doc"):
            text = self._docx.extract(filepath)
            return {"text": text}

        else:
            raise ValueError(f"Unsupported file type: '{ext}'")


# ---------------------------------------------------------------------------
# FinancialExtractor  (regex-based, used by pdf_training_extractor.py)
# ---------------------------------------------------------------------------

class FinancialExtractor:
    """
    Lightweight regex-based financial metric extractor.
    Returns a flat dict of raw numeric values (no nested dicts).
    Used as the first-pass / fallback in the ML training pipeline.
    """

    # Matches patterns like "Revenue: 1,234.56 Cr" or "₹ 500 crore"
    _NUM_RE = re.compile(
        r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh|l|mn|million)?",
        re.IGNORECASE,
    )

    @classmethod
    def _find_value(cls, text: str, *labels: str) -> float:
        """Search text for any of the given labels and return the first number found after it."""
        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
                re.IGNORECASE,
            )
            m = pattern.search(text)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    pass
        return 0.0

    @classmethod
    def extract_from_text(cls, text: str) -> dict:
        """
        Extract basic financial metrics from raw document text.
        Returns a flat dict compatible with _merge_metrics() in pdf_training_extractor.
        """
        if not text:
            return {}

        revenue  = cls._find_value(text, "total revenue", "revenue from operations", "net revenue", "turnover", "revenue")
        ebitda   = cls._find_value(text, "ebitda", "operating profit", "pbdit")
        pat      = cls._find_value(text, "profit after tax", "net profit", "pat")
        debt     = cls._find_value(text, "total debt", "total borrowings", "long term debt")
        net_worth = cls._find_value(text, "net worth", "shareholders equity", "total equity")
        de_ratio  = cls._find_value(text, "debt.equity ratio", "d/e ratio", "debt equity")
        curr_ratio = cls._find_value(text, "current ratio")
        dscr      = cls._find_value(text, "dscr", "debt service coverage")
        icr       = cls._find_value(text, "interest coverage", "icr")
        promoter  = cls._find_value(text, "promoter holding", "promoter shareholding")
        debtors   = cls._find_value(text, "debtors days", "debtor days", "receivable days")

        # Derive margins when possible
        ebitda_margin = round(ebitda / revenue * 100, 2) if revenue else 0.0
        pat_margin    = round(pat / revenue * 100, 2) if revenue else 0.0
        if not de_ratio and debt and net_worth:
            de_ratio = round(debt / max(net_worth, 0.01), 2)

        return {
            "revenue":             {"value": revenue,   "unit": "Cr"},
            "ebitda":              {"value": ebitda,    "unit": "Cr", "margin_pct": ebitda_margin},
            "pat":                 {"value": pat,       "unit": "Cr", "margin_pct": pat_margin},
            "total_debt":          {"value": debt,      "unit": "Cr"},
            "net_worth":           {"value": net_worth, "unit": "Cr"},
            "debt_equity":         de_ratio,
            "current_ratio":       curr_ratio or 0.0,
            "dscr":                dscr or 0.0,
            "interest_coverage_ratio": icr or 0.0,
            "promoter_holding_pct":    promoter or 0.0,
            "debtors_days":            debtors or 0.0,
        }


# ---------------------------------------------------------------------------
# Module-level convenience functions (used by app.py, test_ingestor.py, etc.)
# ---------------------------------------------------------------------------

def _classify_data_type(df: pd.DataFrame) -> str:
    """Heuristic document-type detector based on column names."""
    cols = " ".join(str(c).lower() for c in df.columns)
    if any(k in cols for k in ("credit", "debit", "balance", "transaction", "narration")):
        return "bank_statement"
    if any(k in cols for k in ("gstin", "gst", "igst", "sgst", "cgst", "taxable", "invoice")):
        return "gst_filing"
    if any(k in cols for k in ("income", "itr", "gross total", "tax payable")):
        return "itr"
    return "generic"


def _analyse_bank(df: pd.DataFrame) -> dict:
    """Compute basic bank statement analytics."""
    credit_col = next((c for c in df.columns if "credit" in str(c).lower()), None)
    debit_col  = next((c for c in df.columns if "debit"  in str(c).lower()), None)
    bal_col    = next((c for c in df.columns if "balance" in str(c).lower()), None)

    def _sum(col):
        if col is None:
            return 0.0
        return pd.to_numeric(df[col].str.replace(",", "", regex=False), errors="coerce").fillna(0).sum()

    total_credits = float(_sum(credit_col))
    total_debits  = float(_sum(debit_col))
    balances = (
        pd.to_numeric(df[bal_col].str.replace(",", "", regex=False), errors="coerce").fillna(0)
        if bal_col else pd.Series(dtype=float)
    )

    return {
        "type": "Bank Statement Analysis",
        "total_credits":    total_credits,
        "total_debits":     total_debits,
        "net_cash_flow":    round(total_credits - total_debits, 2),
        "avg_balance":      float(balances.mean()) if not balances.empty else 0.0,
        "min_balance":      float(balances.min())  if not balances.empty else 0.0,
        "max_balance":      float(balances.max())  if not balances.empty else 0.0,
        "credit_count":     int((pd.to_numeric(df[credit_col].str.replace(",", "", regex=False) if credit_col else pd.Series(), errors="coerce") > 0).sum()) if credit_col else 0,
    }


def _analyse_gst(df: pd.DataFrame) -> dict:
    """Compute basic GST filing analytics."""
    taxable_col = next(
        (c for c in df.columns if any(k in str(c).lower() for k in ("taxable", "taxable_value", "taxable value"))),
        None,
    )
    tax_col = next(
        (c for c in df.columns if any(k in str(c).lower() for k in ("total_tax", "total tax", "igst", "tax amount"))),
        None,
    )
    party_col = next(
        (c for c in df.columns if any(k in str(c).lower() for k in ("gstin", "party", "supplier", "recipient"))),
        None,
    )

    def _col_sum(col):
        if col is None:
            return 0.0
        return float(pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0).sum())

    total_taxable = _col_sum(taxable_col)
    total_tax     = _col_sum(tax_col)
    unique_parties = int(df[party_col].nunique()) if party_col else 0

    return {
        "type": "GST Filing Analysis",
        "total_taxable_value": total_taxable,
        "total_tax":           total_tax,
        "unique_parties":      unique_parties,
        "monthly_avg":         round(total_taxable / 12, 2) if total_taxable else 0.0,
        "volatility":          0.0,
    }


def ingest_document(filepath: str) -> dict:
    """
    Ingest a single document and return a unified result dict expected by
    app.py, test_ingestor.py, and other pipeline consumers.

    Result keys (varies by file type):
      PDF  → text, text_length, page_count, table_count, metadata, rule_based_metrics, data_type, filename
      CSV/XLSX → row_count, columns, data_type, preview, analysis, text, filename
      DOCX → text, text_length, data_type, filename
    """
    from pathlib import Path as _Path

    ext      = _Path(filepath).suffix.lower()
    filename = _Path(filepath).name
    ingestor = DataIngestor()

    try:
        raw = ingestor.ingest(filepath)
    except Exception as e:
        return {"error": str(e), "filename": filename, "data_type": "error"}

    # ── PDF ──
    if ext == ".pdf":
        text = raw.get("text", "")
        tables = raw.get("tables", [])
        result = {
            "filename":          filename,
            "data_type":         "annual_report",
            "text":              text,
            "text_length":       len(text),
            "page_count":        max((t.get("page", 0) for t in tables), default=0) if tables else 0,
            "table_count":       len(tables),
            "extraction_method": raw.get("extraction_method"),
            "metadata":          {"detected_type": "annual_report", "errors": raw.get("errors", [])},
            "rule_based_metrics": FinancialExtractor.extract_from_text(text) if text else {},
        }
        return result

    # ── CSV / Excel ──
    if ext in (".csv", ".xlsx", ".xls", ".xlsm"):
        df: pd.DataFrame = raw.get("dataframe", pd.DataFrame())
        data_type = _classify_data_type(df)

        if data_type == "bank_statement":
            analysis = _analyse_bank(df)
        elif data_type == "gst_filing":
            analysis = _analyse_gst(df)
        else:
            analysis = {"type": "Generic Tabular Data"}

        # Build a text summary for downstream AI (keep it short)
        text_summary = f"Document type: {data_type}\n" + df.head(20).to_string(index=False)

        return {
            "filename":   filename,
            "data_type":  data_type,
            "row_count":  len(df),
            "columns":    list(df.columns),
            "preview":    df.head(10).to_dict(orient="records"),
            "analysis":   analysis,
            "text":       text_summary,
            "dataframe":  df,
        }

    # ── DOCX ──
    if ext in (".docx", ".doc"):
        text = raw.get("text", "")
        return {
            "filename":    filename,
            "data_type":   "document",
            "text":        text,
            "text_length": len(text),
            "table_count": 0,
        }

    # ── Fallback ──
    return {**raw, "filename": filename, "data_type": "generic"}


def ingest_multiple(filepaths: list) -> list:
    """
    Ingest a list of file paths and return a list of ingest_document results.
    Skips files that cannot be found or fail to ingest gracefully.
    """
    results = []
    for fp in filepaths:
        if not os.path.isfile(fp):
            logger.warning(f"File not found, skipping: {fp}")
            continue
        result = ingest_document(fp)
        results.append(result)
        logger.info(f"Ingested: {fp} → type={result.get('data_type', '?')}")
    return results

