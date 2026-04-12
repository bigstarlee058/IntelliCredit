"""
Data Ingestor - Pillar 1
=========================
Multi-format document parser for credit analysis.
Handles: PDFs (annual reports, legal docs, scanned), Excel/CSV (GST, bank stmts, ITR),
DOCX documents, and text-based documents.

FIX HISTORY:
  - Fix 1: Robust CSV reading with encoding fallback chain
  - Fix 2: Multi-sheet Excel support (reads all sheets, picks best)
  - Fix 3: _find_true_headers handles NaN/missing headers
  - Fix 4: _parse_gst applies _clean_numeric before aggregation
  - Fix 5: _parse_bank_statement uses _clean_numeric consistently
  - Fix 6: DOCX parser added via python-docx
  - Fix 7: Structured data generates a 'text' field for AI/LLM pipeline
  - Fix 8: General robustness (try/except, logging, edge cases)
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Lazy imports for heavy PDF libs ──
_fitz = None
_pdfplumber = None


def _get_fitz():
    global _fitz
    if _fitz is None:
        import fitz
        _fitz = fitz
    return _fitz


def _get_pdfplumber():
    global _pdfplumber
    if _pdfplumber is None:
        import pdfplumber
        _pdfplumber = pdfplumber
    return _pdfplumber


# ═══════════════════════════════════════════════════════════════════
#  PDF PARSING
# ═══════════════════════════════════════════════════════════════════

class PDFIngestor:
    """Extract text, tables, and metadata from PDF documents."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.text = ""
        self.tables = []
        self.metadata = {}
        self.pages = []

    def extract(self) -> dict:
        """Run full extraction pipeline on the PDF."""
        logger.info(f"Extracting from PDF: {self.filename}")
        self._extract_with_fitz()

        # If fitz got no text, try pdfplumber as standalone (not just table extraction)
        if not self.text or len(self.text.strip()) < 50:
            logger.warning(f"PyMuPDF got minimal text ({len(self.text)} chars), trying pdfplumber...")
            self._fallback_pdfplumber()

        self._extract_tables()
        self._classify_document()
        return self.to_dict()

    def _extract_with_fitz(self):
        """Primary extraction using PyMuPDF (fitz) with OCR fallback."""
        try:
            fitz = _get_fitz()
            doc = fitz.open(self.filepath)
            self.metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "page_count": len(doc),
                "creation_date": doc.metadata.get("creationDate", ""),
            }
            full_text = []
            ocr_pages = 0
            for page_num, page in enumerate(doc):
                page_text = page.get_text("text")
                
                # Selective OCR: run only on image-based pages (< 50 chars) up to max 10 pages
                if len(page_text.strip()) < 50 and ocr_pages < 10:
                    ocr_text = self._ocr_page(page)
                    if ocr_text and len(ocr_text) > len(page_text):
                        page_text = ocr_text
                        ocr_pages += 1
                
                self.pages.append({
                    "page_number": page_num + 1,
                    "text": page_text,
                    "char_count": len(page_text),
                })
                full_text.append(page_text)
            self.text = "\n\n".join(full_text)
            if ocr_pages:
                self.metadata["ocr_pages"] = ocr_pages
                logger.info(f"OCR applied to {ocr_pages} image-based pages in {self.filename}")
            doc.close()
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed for {self.filename}: {e}")
            self._fallback_pdfplumber()
    
    def _ocr_page(self, page) -> str:
        """Run OCR on a PDF page image using pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            import io
            
            # Render page as image at 300 DPI for good OCR quality
            mat = _get_fitz().Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Run OCR
            text = pytesseract.image_to_string(img, lang='eng')
            return text.strip()
        except ImportError:
            logger.debug("pytesseract not available for OCR")
            return ""
        except Exception as e:
            logger.debug(f"OCR failed for page: {e}")
            return ""

    def _fallback_pdfplumber(self):
        """Fallback extraction using pdfplumber (better for scanned docs)."""
        try:
            pdfplumber = _get_pdfplumber()
            with pdfplumber.open(self.filepath) as pdf:
                self.metadata = {
                    "page_count": len(pdf.pages),
                }
                full_text = []
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    # pdfplumber has better table-aware extraction
                    if not page_text.strip():
                        # Try extracting text with different settings
                        try:
                            page_text = page.extract_text(
                                x_tolerance=3, y_tolerance=3
                            ) or ""
                        except Exception:
                            page_text = ""
                    self.pages.append({
                        "page_number": page_num + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                    })
                    full_text.append(page_text)
                self.text = "\n\n".join(full_text)
                logger.info(f"pdfplumber extracted {len(self.text)} chars from {self.filename}")
        except Exception as e:
            logger.error(f"pdfplumber extraction also failed for {self.filename}: {e}")

    def _extract_tables(self):
        """Extract tables from the PDF."""
        try:
            pdfplumber = _get_pdfplumber()
            with pdfplumber.open(self.filepath) as pdf:
                # FAST MODE: Limit table extraction to first 30 pages to prevent hanging on large reports
                pages_to_process = pdf.pages[:30] if len(pdf.pages) > 30 else pdf.pages
                for page_num, page in enumerate(pages_to_process):
                    try:
                        page_tables = page.extract_tables()
                    except Exception as e:
                        logger.debug(f"Table extraction failed on page {page_num+1}: {e}")
                        continue
                    for t_idx, table in enumerate(page_tables or []):
                        if table and len(table) > 1:
                            # Convert to DataFrame
                            headers = table[0] if table[0] else [f"Col{i}" for i in range(len(table[1]))]
                            headers = [str(h).strip() if h else f"Col{i}" for i, h in enumerate(headers)]
                            rows = table[1:]
                            try:
                                df = pd.DataFrame(rows, columns=headers[:len(rows[0])] if rows else headers)
                                self.tables.append({
                                    "page": page_num + 1,
                                    "table_index": t_idx,
                                    "headers": headers,
                                    "data": df.to_dict(orient="records"),
                                    "row_count": len(rows),
                                })
                            except Exception:
                                self.tables.append({
                                    "page": page_num + 1,
                                    "table_index": t_idx,
                                    "headers": headers,
                                    "data": [dict(zip(headers, row)) for row in rows if row],
                                    "row_count": len(rows),
                                })
        except Exception as e:
            logger.warning(f"Table extraction failed for {self.filename}: {e}")

    def _classify_document(self):
        """Classify the document type based on content."""
        text_lower = self.text.lower()
        keywords = {
            "annual_report": ["annual report", "director's report", "auditor's report",
                              "balance sheet", "profit and loss", "cash flow statement"],
            "financial_statement": ["balance sheet", "profit and loss", "schedule",
                                    "notes to accounts", "significant accounting"],
            "sanction_letter": ["sanction", "credit facility", "terms and conditions",
                                "security", "disbursement", "covenant"],
            "legal_notice": ["legal notice", "court", "petition", "plaintiff",
                             "defendant", "arbitration"],
            "gst_filing": ["gstr", "gstin", "taxable value", "igst", "cgst", "sgst"],
            "bank_statement": ["opening balance", "closing balance", "transaction",
                               "debit", "credit", "cheque"],
            "rating_report": ["rating", "credit rating", "crisil", "icra", "care",
                              "india ratings", "brickwork"],
            "board_minutes": ["board of directors", "meeting", "resolution",
                              "quorum", "agenda"],
        }

        scores = {}
        for doc_type, kws in keywords.items():
            score = sum(1 for kw in kws if kw in text_lower)
            if score > 0:
                scores[doc_type] = score

        if scores:
            self.metadata["detected_type"] = max(scores, key=scores.get)
            self.metadata["type_confidence"] = max(scores.values()) / len(keywords[self.metadata["detected_type"]])
        else:
            self.metadata["detected_type"] = "unknown"
            self.metadata["type_confidence"] = 0

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "metadata": self.metadata,
            "text": self.text,
            "text_length": len(self.text),
            "tables": self.tables,
            "table_count": len(self.tables),
            "page_count": len(self.pages),
        }


# ═══════════════════════════════════════════════════════════════════
#  STRUCTURED DATA PARSING (Excel / CSV) — FIXED
# ═══════════════════════════════════════════════════════════════════

class StructuredDataIngestor:
    """Parse GST filings, bank statements, ITRs from Excel/CSV."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.ext = os.path.splitext(filepath)[1].lower()

    # ── FIX 1: Robust CSV reading with encoding fallback ──
    def _read_csv_robust(self, filepath: str) -> pd.DataFrame:
        """Read CSV with multiple encoding attempts and error recovery."""
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                df = pd.read_csv(
                    filepath,
                    encoding=encoding,
                    on_bad_lines="skip",
                    engine="python",
                    dtype=str,  # Read everything as string first to avoid type errors
                )
                if len(df) > 0 and len(df.columns) > 0:
                    logger.info(f"CSV read OK with encoding={encoding}: {len(df)} rows, {len(df.columns)} cols")
                    return df
            except UnicodeDecodeError:
                logger.debug(f"CSV encoding {encoding} failed, trying next...")
                continue
            except pd.errors.EmptyDataError:
                logger.warning(f"CSV file is empty: {filepath}")
                return pd.DataFrame()
            except Exception as e:
                logger.debug(f"CSV read with {encoding} failed: {e}")
                continue

        # Ultimate fallback: binary read with ignore errors
        logger.warning(f"All encodings failed for {filepath}, using latin-1 with error ignore")
        try:
            df = pd.read_csv(
                filepath,
                encoding="latin-1",
                on_bad_lines="skip",
                engine="python",
                dtype=str,
            )
            return df
        except Exception as e:
            logger.error(f"CSV read completely failed for {filepath}: {e}")
            return pd.DataFrame()

    # ── FIX 2: Multi-sheet Excel support ──
    def _read_excel_robust(self, filepath: str) -> pd.DataFrame:
        """Read Excel with multi-sheet support, picking the best sheet."""
        try:
            # Read all sheets
            all_sheets = pd.read_excel(
                filepath,
                sheet_name=None,  # Read ALL sheets
                dtype=str,  # Read as strings first to avoid type coercion issues
                engine="openpyxl" if self.ext == ".xlsx" else None,
            )

            if not all_sheets:
                logger.warning(f"No sheets found in Excel file: {filepath}")
                return pd.DataFrame()

            # Pick the sheet with the most data (rows × columns)
            best_sheet_name = None
            best_size = 0
            best_df = None

            for sheet_name, df in all_sheets.items():
                size = len(df) * len(df.columns)
                logger.info(f"  Sheet '{sheet_name}': {len(df)} rows × {len(df.columns)} cols = {size}")
                if size > best_size:
                    best_size = size
                    best_sheet_name = sheet_name
                    best_df = df

            if best_df is not None:
                logger.info(f"Selected sheet '{best_sheet_name}' ({len(best_df)} rows) from {self.filename}")

                # If there are multiple data sheets, try to concatenate them
                if len(all_sheets) > 1:
                    # Check if other sheets have same columns (same format = multiple months/years)
                    compatible_dfs = [best_df]
                    best_cols = set(str(c).lower().strip() for c in best_df.columns)
                    for sheet_name, df in all_sheets.items():
                        if sheet_name == best_sheet_name:
                            continue
                        sheet_cols = set(str(c).lower().strip() for c in df.columns)
                        # If > 80% column overlap AND same shape, sheets are likely compatible
                        if len(best_cols & sheet_cols) >= len(best_cols) * 0.8 and len(df) > 0 and len(df.columns) == len(best_df.columns):
                            try:
                                df.columns = best_df.columns  # Force exact column alignment
                                compatible_dfs.append(df)
                            except Exception:
                                pass
                    if len(compatible_dfs) > 1:
                        combined_df = pd.concat(compatible_dfs, ignore_index=True)
                        logger.info(f"Combined {len(compatible_dfs)} compatible sheets → {len(combined_df)} total rows")
                        return combined_df

                return best_df
            return pd.DataFrame()

        except ImportError:
            logger.error("openpyxl not installed. Install with: pip install openpyxl")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Excel read failed for {filepath}: {e}")
            # Fallback: try reading just the first sheet with defaults
            try:
                return pd.read_excel(filepath, dtype=str)
            except Exception as e2:
                logger.error(f"Excel fallback also failed: {e2}")
                return pd.DataFrame()

    # ── FIX 3: Handle NaN/missing headers ──
    def _find_true_headers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Find the true header row by looking for common keywords in the first few rows."""
        if df.empty:
            return df

        keywords = [
            "date", "transaction", "debit", "credit", "balance", "narration",
            "particulars", "gstin", "amount", "income", "taxable", "description",
            "deposit", "withdrawal", "cheque", "reference", "value", "total",
            "invoice", "party", "tax", "igst", "cgst", "sgst",
        ]
        
        # Clean current column names: replace NaN with Col_i, strip whitespace
        clean_cols = []
        for i, c in enumerate(df.columns):
            if pd.isna(c) or str(c).strip() == "" or str(c).startswith("Unnamed"):
                clean_cols.append(f"Col{i}")
            else:
                clean_cols.append(str(c).strip())
        df.columns = clean_cols

        # Check current columns first
        cols_lower = " ".join([str(c).lower() for c in df.columns])
        if sum(1 for kw in keywords if kw in cols_lower) >= 2:
            return df

        # Check first 15 rows for the actual header row
        for i in range(min(15, len(df))):
            row_vals = df.iloc[i].values
            # Convert to strings, handling NaN
            row_str = " ".join([str(val).lower() if pd.notna(val) else "" for val in row_vals])
            if sum(1 for kw in keywords if kw in row_str) >= 2:
                # Found the header row
                new_header = []
                for j, val in enumerate(row_vals):
                    if pd.notna(val) and str(val).strip():
                        new_header.append(str(val).strip())
                    else:
                        new_header.append(f"Col{j}")
                df = df[i+1:].copy()
                df.columns = new_header[:len(df.columns)]
                df.reset_index(drop=True, inplace=True)
                logger.info(f"Found true headers at row {i}: {new_header[:5]}...")
                return df
                
        return df

    def _clean_numeric(self, series):
        """Clean numeric values that may have commas, currency symbols, or text."""
        if series.dtype == 'object' or series.dtype == 'string':
            series = series.astype(str)
            # Remove common currency symbols and formatting
            series = series.str.replace(',', '', regex=False)
            series = series.str.replace('$', '', regex=False)
            series = series.str.replace('₹', '', regex=False)
            series = series.str.replace('Rs.', '', regex=False)
            series = series.str.replace('Rs', '', regex=False)
            series = series.str.replace('INR', '', regex=False)
            series = series.str.replace(' ', '', regex=False)
            # Handle bracket negatives: (1234) → -1234
            mask = series.str.match(r'^\(.*\)$', na=False)
            series = series.str.strip('()')
            series = pd.to_numeric(series, errors="coerce")
            series[mask] = -series[mask]
            return series.fillna(0)
        return pd.to_numeric(series, errors="coerce").fillna(0)

    # ── FIX 7: Generate text representation of structured data ──
    def _generate_text_from_df(self, df: pd.DataFrame, data_type: str) -> str:
        """Generate a text representation of the DataFrame for AI/LLM pipeline."""
        parts = []
        parts.append(f"=== {data_type.upper().replace('_', ' ')} DATA ===")
        parts.append(f"File: {self.filename}")
        parts.append(f"Rows: {len(df)}, Columns: {len(df.columns)}")
        parts.append(f"Column Names: {', '.join(str(c) for c in df.columns)}")
        parts.append("")

        # Include column data types summary
        parts.append("Column Summary:")
        for col in df.columns[:20]:  # Max 20 columns
            try:
                non_null = df[col].notna().sum()
                sample_vals = df[col].dropna().head(3).tolist()
                sample_str = ", ".join(str(v)[:50] for v in sample_vals)
                parts.append(f"  - {col}: {non_null} values, e.g. [{sample_str}]")
            except Exception:
                parts.append(f"  - {col}: (could not summarize)")
        parts.append("")

        # Include first 30 rows as tabular text
        parts.append("Data Preview (first 30 rows):")
        try:
            preview = df.head(30).to_string(index=False, max_colwidth=40)
            parts.append(preview)
        except Exception:
            # Fallback: CSV-style
            parts.append(df.head(30).to_csv(index=False))

        # Include numeric statistics
        try:
            numeric_df = df.copy()
            for col in numeric_df.columns:
                numeric_df[col] = pd.to_numeric(numeric_df[col].astype(str).str.replace(',', ''), errors='coerce')
            numeric_cols = numeric_df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                parts.append("")
                parts.append("Numeric Statistics:")
                stats = numeric_df[numeric_cols].describe().to_string()
                parts.append(stats)
        except Exception:
            pass

        return "\n".join(parts)

    def extract(self) -> dict:
        logger.info(f"Extracting structured data: {self.filename}")

        # ── Read the file ──
        df = pd.DataFrame()
        if self.ext == ".csv":
            df = self._read_csv_robust(self.filepath)
        elif self.ext in (".xlsx", ".xls"):
            df = self._read_excel_robust(self.filepath)
        else:
            return {"error": f"Unsupported format: {self.ext}", "filename": self.filename}

        if df.empty:
            logger.warning(f"No data extracted from {self.filename}")
            return {
                "filename": self.filename,
                "data_type": "empty",
                "error": "No data could be read from the file. Check file format and encoding.",
                "columns": [],
                "row_count": 0,
                "preview": [],
                "analysis": {},
                "text": "",
            }

        # Drop completely empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")

        df = self._find_true_headers(df)
        data_type = self._detect_data_type(df)
        
        # Safe column casting to string for preview
        cols_as_str = [str(c) for c in df.columns]
        df.columns = cols_as_str

        # Generate text representation for AI pipeline (FIX 7)
        text_repr = self._generate_text_from_df(df, data_type)
        
        result = {
            "filename": self.filename,
            "data_type": data_type,
            "columns": cols_as_str,
            "row_count": len(df),
            "preview": df.head(50).to_dict(orient="records"),  # Increased from 20 to 50
            "statistics": {},
            "text": text_repr,  # NEW: text field for AI/LLM pipeline
        }

        # Type-specific parsing
        try:
            if data_type == "gst_filing":
                result["analysis"] = self._parse_gst(df)
            elif data_type == "bank_statement":
                result["analysis"] = self._parse_bank_statement(df)
            elif data_type == "itr":
                result["analysis"] = self._parse_itr(df)
            else:
                result["analysis"] = self._generic_analysis(df)
        except Exception as e:
            logger.error(f"Analysis failed for {self.filename}: {e}")
            result["analysis"] = {"type": "Analysis Error", "error": str(e)}

        # Add basic statistics for all files
        try:
            numeric_df = df.copy()
            for col in numeric_df.columns:
                numeric_df[col] = pd.to_numeric(
                    numeric_df[col].astype(str).str.replace(',', '').str.replace('₹', '').str.strip(),
                    errors='coerce'
                )
            num_cols = numeric_df.select_dtypes(include=["number"]).columns
            if len(num_cols) > 0:
                result["statistics"] = {
                    col: {
                        "mean": round(float(numeric_df[col].mean()), 2) if pd.notna(numeric_df[col].mean()) else 0,
                        "sum": round(float(numeric_df[col].sum()), 2),
                        "min": round(float(numeric_df[col].min()), 2) if pd.notna(numeric_df[col].min()) else 0,
                        "max": round(float(numeric_df[col].max()), 2) if pd.notna(numeric_df[col].max()) else 0,
                    }
                    for col in list(num_cols)[:10]
                }
        except Exception as e:
            logger.debug(f"Statistics generation failed: {e}")

        return result

    def _detect_data_type(self, df: pd.DataFrame) -> str:
        cols_lower = [str(c).lower() for c in df.columns]
        col_str = " ".join(cols_lower)

        # Also check first few rows for type hints (some files have generic column names)
        row_str = ""
        try:
            for i in range(min(5, len(df))):
                row_str += " ".join(str(v).lower() for v in df.iloc[i].values if pd.notna(v)) + " "
        except Exception:
            pass
        combined = col_str + " " + row_str

        if any(kw in combined for kw in ["gstin", "gstr", "taxable value", "igst", "cgst"]):
            return "gst_filing"
        elif any(kw in combined for kw in ["transaction", "debit", "credit", "balance", "narration",
                                            "deposit", "withdrawal", "withdrawl", "cheque", "description"]):
            return "bank_statement"
        elif any(kw in combined for kw in ["income", "deduction", "tax payable", "assessment"]):
            return "itr"
        return "generic"

    # ── FIX 4: _parse_gst applies _clean_numeric before aggregation ──
    def _parse_gst(self, df: pd.DataFrame) -> dict:
        """Parse GST filing data and compute key metrics."""
        analysis = {"type": "GST Filing Analysis"}
        try:
            # Try to find revenue columns
            rev_cols = [c for c in df.columns if any(kw in str(c).lower()
                        for kw in ["taxable", "value", "amount", "total"])]
            if rev_cols:
                col = rev_cols[0]
                clean_vals = self._clean_numeric(df[col])
                analysis["total_taxable_value"] = float(clean_vals.sum())
                non_zero = clean_vals[clean_vals > 0]
                analysis["monthly_avg"] = float(non_zero.mean()) if len(non_zero) > 0 else 0
                analysis["max_month"] = float(clean_vals.max())
                analysis["min_month"] = float(clean_vals[clean_vals > 0].min()) if (clean_vals > 0).any() else 0
                mean_val = non_zero.mean() if len(non_zero) > 0 else 0
                analysis["volatility"] = float(non_zero.std() / mean_val) if mean_val != 0 else 0

            tax_cols = [c for c in df.columns if any(kw in str(c).lower()
                        for kw in ["igst", "cgst", "sgst", "tax"])]
            if tax_cols:
                total_tax = 0
                for c in tax_cols:
                    total_tax += float(self._clean_numeric(df[c]).sum())
                analysis["total_tax"] = total_tax

            # Count unique GSTINs if available
            gstin_cols = [c for c in df.columns if "gstin" in str(c).lower()]
            if gstin_cols:
                unique_gstins = df[gstin_cols[0]].dropna().nunique()
                analysis["unique_parties"] = int(unique_gstins)

        except Exception as e:
            logger.error(f"GST parsing error: {e}")
            analysis["error"] = str(e)
        return analysis

    @staticmethod
    def _col_matches(col_name: str, keywords: list) -> bool:
        """Check if a column name matches any keyword using word-boundary-aware matching.
        
        Short keywords like 'cr', 'dr' are matched with word boundaries or as
        suffixes (e.g. 'Debit_Cr' contains '_cr'), NOT as substrings of unrelated
        words (e.g. 'Description' should NOT match 'cr').
        """
        import re as _re
        col_lower = str(col_name).lower().strip()
        for kw in keywords:
            if len(kw) <= 2:
                # Short keywords: require word boundary (underscore, space, start/end)
                # Matches: "Credit_Cr", "Cr", "cr", "Amount_CR" but NOT "Description", "Increase"
                if _re.search(rf'(?:^|[_\s])' + _re.escape(kw) + rf'(?:$|[_\s])', col_lower):
                    return True
                # Also match if column name IS the keyword exactly
                if col_lower == kw:
                    return True
            else:
                # Longer keywords: substring match is fine
                if kw in col_lower:
                    return True
        return False

    # ── FIX 5: _parse_bank_statement uses _clean_numeric consistently ──
    def _parse_bank_statement(self, df: pd.DataFrame) -> dict:
        """Parse bank statement and compute cash flow metrics."""
        analysis = {"type": "Bank Statement Analysis"}
        try:
            # Match credit/deposit columns using word-boundary-aware matching
            # This prevents 'cr' from matching 'Description', 'dr' from matching random words
            credit_cols = [c for c in df.columns if self._col_matches(c, ["credit", "deposit", "cr"])]
            debit_cols = [c for c in df.columns if self._col_matches(c, ["debit", "withdrawal", "withdrawl", "dr"])]
            balance_cols = [c for c in df.columns if "balance" in str(c).lower()]

            logger.info(f"Bank stmt columns detected — credit: {credit_cols}, debit: {debit_cols}, balance: {balance_cols}")

            # If no obvious columns, try "Amount" column with Dr/Cr indicators
            if not credit_cols and not debit_cols:
                amount_cols = [c for c in df.columns if "amount" in str(c).lower()]
                type_cols = [c for c in df.columns if any(kw in str(c).lower()
                            for kw in ["type", "dr/cr", "cr/dr", "transaction type"])]
                if amount_cols and type_cols:
                    logger.info("Using Amount + Type column pattern for bank statement")
                    amounts = self._clean_numeric(df[amount_cols[0]])
                    types = df[type_cols[0]].astype(str).str.lower()
                    cr_mask = types.str.contains("cr|credit|deposit", na=False)
                    dr_mask = types.str.contains("dr|debit|withdrawal", na=False)
                    analysis["total_credits"] = float(amounts[cr_mask].sum())
                    analysis["total_debits"] = float(amounts[dr_mask].sum())
                    analysis["avg_credit"] = float(amounts[cr_mask].mean()) if cr_mask.any() else 0
                    analysis["avg_debit"] = float(amounts[dr_mask].mean()) if dr_mask.any() else 0
                    analysis["credit_count"] = int(cr_mask.sum())
                    analysis["net_cash_flow"] = analysis["total_credits"] - analysis["total_debits"]
                    return analysis

            if credit_cols:
                credits = self._clean_numeric(df[credit_cols[0]])
                analysis["total_credits"] = float(credits.sum())
                positive_credits = credits[credits > 0]
                analysis["avg_credit"] = float(positive_credits.mean()) if len(positive_credits) > 0 else 0
                analysis["credit_count"] = int((credits > 0).sum())

            if debit_cols:
                debits = self._clean_numeric(df[debit_cols[0]])
                analysis["total_debits"] = float(debits.sum())
                positive_debits = debits[debits > 0]
                analysis["avg_debit"] = float(positive_debits.mean()) if len(positive_debits) > 0 else 0

            if balance_cols:
                balances = self._clean_numeric(df[balance_cols[0]])
                balances = balances[balances != 0]
                if len(balances) > 0:
                    analysis["avg_balance"] = float(balances.mean())
                    analysis["min_balance"] = float(balances.min())
                    analysis["max_balance"] = float(balances.max())

            # Net cash flow
            if "total_credits" in analysis and "total_debits" in analysis:
                analysis["net_cash_flow"] = analysis["total_credits"] - analysis["total_debits"]

            # Transaction count
            analysis["transaction_count"] = len(df)

        except Exception as e:
            logger.error(f"Bank statement parsing error: {e}")
            analysis["error"] = str(e)
        return analysis

    def _parse_itr(self, df: pd.DataFrame) -> dict:
        """Parse Income Tax Return data."""
        analysis = {"type": "ITR Analysis"}
        try:
            inc_cols = [c for c in df.columns if "income" in str(c).lower()]
            if inc_cols:
                analysis["total_income"] = float(self._clean_numeric(df[inc_cols[0]]).sum())
            
            tax_cols = [c for c in df.columns if any(kw in str(c).lower()
                       for kw in ["tax", "payable", "paid"])]
            if tax_cols:
                analysis["total_tax"] = float(self._clean_numeric(df[tax_cols[0]]).sum())
        except Exception as e:
            analysis["error"] = str(e)
        return analysis

    def _generic_analysis(self, df: pd.DataFrame) -> dict:
        """Generic analysis for unrecognized data."""
        analysis = {"type": "Generic Data Analysis"}
        try:
            # Convert all columns to numeric where possible
            numeric_df = df.copy()
            for col in numeric_df.columns:
                numeric_df[col] = self._clean_numeric(numeric_df[col])
            
            numeric_cols = numeric_df.select_dtypes(include=["number"]).columns.tolist()
            for col in numeric_cols[:10]:
                non_zero = numeric_df[col][numeric_df[col] != 0]
                if len(non_zero) > 0:
                    analysis[col] = {
                        "mean": round(float(non_zero.mean()), 2),
                        "sum": round(float(non_zero.sum()), 2),
                        "min": round(float(non_zero.min()), 2),
                        "max": round(float(non_zero.max()), 2),
                        "count": int(len(non_zero)),
                    }
        except Exception as e:
            analysis["error"] = str(e)
        return analysis


# ═══════════════════════════════════════════════════════════════════
#  DOCX PARSING (FIX 6)
# ═══════════════════════════════════════════════════════════════════

class DocxIngestor:
    """Extract text from Word (.docx) documents."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

    def extract(self) -> dict:
        """Extract text and tables from a DOCX file."""
        try:
            from docx import Document
        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            return {
                "filename": self.filename,
                "error": "python-docx not installed",
                "text": "",
                "text_length": 0,
            }

        try:
            doc = Document(self.filepath)
            
            # Extract paragraphs
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            # Extract tables
            tables = []
            for t_idx, table in enumerate(doc.tables):
                rows_data = []
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells]
                    rows_data.append(row_text)
                if rows_data:
                    headers = rows_data[0] if rows_data else []
                    tables.append({
                        "table_index": t_idx,
                        "headers": headers,
                        "data": [dict(zip(headers, row)) for row in rows_data[1:]] if len(rows_data) > 1 else [],
                        "row_count": len(rows_data) - 1,
                    })

            full_text = "\n".join(paragraphs)
            
            # Also include table content in the text
            for table in tables:
                full_text += "\n\n" + " | ".join(table["headers"])
                for row_dict in table["data"]:
                    full_text += "\n" + " | ".join(row_dict.values())

            logger.info(f"DOCX extracted: {len(paragraphs)} paragraphs, {len(tables)} tables, {len(full_text)} chars")

            return {
                "filename": self.filename,
                "text": full_text,
                "text_length": len(full_text),
                "tables": tables,
                "table_count": len(tables),
                "metadata": {
                    "paragraph_count": len(paragraphs),
                    "detected_type": "document",
                },
            }
        except Exception as e:
            logger.error(f"DOCX extraction failed for {self.filename}: {e}")
            return {
                "filename": self.filename,
                "error": str(e),
                "text": "",
                "text_length": 0,
            }


# ═══════════════════════════════════════════════════════════════════
#  FINANCIAL METRIC EXTRACTION (Rule-Based)
# ═══════════════════════════════════════════════════════════════════

class FinancialExtractor:
    """Rule-based extraction of financial metrics from text."""

    # Common Indian financial terms regex patterns
    PATTERNS = {
        "revenue": [
            r"(?:total\s+)?(?:revenue|turnover|sales|income\s+from\s+operations)[\s:]*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)\s*(?:Cr|Crore|Lakh|L|cr)",
        ],
        "pat": [
            r"(?:profit\s+after\s+tax|PAT|net\s+profit)[\s:]*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)\s*(?:Cr|Crore|Lakh|cr)",
        ],
        "ebitda": [
            r"(?:EBITDA|earnings\s+before)[\s:]*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)\s*(?:Cr|Crore|Lakh|cr)",
        ],
        "total_debt": [
            r"(?:total\s+(?:debt|borrowings?))[\s:]*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)\s*(?:Cr|Crore|Lakh|cr)",
        ],
        "net_worth": [
            r"(?:net\s+worth|shareholders?\s+funds?)[\s:]*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)\s*(?:Cr|Crore|Lakh|cr)",
        ],
        "debt_equity": [
            r"(?:debt[\s-]equity\s+ratio|D/E\s+ratio)[\s:]*([\d]+\.?\d*)",
        ],
        "current_ratio": [
            r"(?:current\s+ratio)[\s:]*([\d]+\.?\d*)",
        ],
    }

    @classmethod
    def extract_from_text(cls, text: str) -> dict:
        """Extract financial metrics using regex patterns."""
        metrics = {}
        for metric_name, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1).replace(",", ""))
                        metrics[metric_name] = value
                    except ValueError:
                        pass
                    break
        return metrics


# ═══════════════════════════════════════════════════════════════════
#  UNIFIED INGESTION PIPELINE
# ═══════════════════════════════════════════════════════════════════

def ingest_document(filepath: str) -> dict:
    """Main entry point: detect file type and route to appropriate parser."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        ingestor = PDFIngestor(filepath)
        result = ingestor.extract()
        # Also run rule-based extraction
        result["rule_based_metrics"] = FinancialExtractor.extract_from_text(result.get("text", ""))
        return result
    elif ext in (".csv", ".xlsx", ".xls"):
        ingestor = StructuredDataIngestor(filepath)
        return ingestor.extract()
    elif ext in (".docx", ".doc"):
        ingestor = DocxIngestor(filepath)
        result = ingestor.extract()
        # Also run rule-based extraction on docx text
        if result.get("text"):
            result["rule_based_metrics"] = FinancialExtractor.extract_from_text(result["text"])
        return result
    elif ext == ".txt":
        try:
            # Try multiple encodings for text files too
            text = ""
            for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    with open(filepath, "r", encoding=enc, errors="ignore") as f:
                        text = f.read()
                    if text:
                        break
                except Exception:
                    continue
            return {
                "filename": os.path.basename(filepath),
                "data_type": "text",
                "text": text,
                "text_length": len(text),
                "rule_based_metrics": FinancialExtractor.extract_from_text(text),
            }
        except Exception as e:
            return {"filename": os.path.basename(filepath), "error": str(e), "text": ""}
    elif ext == ".json":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Generate text from JSON for AI pipeline
            text = json.dumps(data, indent=2, default=str)
            return {
                "filename": os.path.basename(filepath),
                "data_type": "json",
                "data": data,
                "text": text,
                "text_length": len(text),
            }
        except Exception as e:
            return {"filename": os.path.basename(filepath), "error": str(e)}
    else:
        return {"error": f"Unsupported file type: {ext}", "filename": os.path.basename(filepath)}


def ingest_multiple(filepaths: list) -> list:
    """Ingest multiple documents and return combined results."""
    results = []
    for fp in filepaths:
        try:
            logger.info(f"Ingesting: {os.path.basename(fp)}")
            result = ingest_document(fp)
            result["status"] = "success"
        except Exception as e:
            logger.error(f"Failed to ingest {os.path.basename(fp)}: {e}")
            result = {"filename": os.path.basename(fp), "status": "error", "error": str(e)}
        results.append(result)
    return results
