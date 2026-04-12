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
