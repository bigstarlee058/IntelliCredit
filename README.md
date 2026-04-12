# IntelliCredit — AI-Powered Credit Analysis Pipeline for Indian MSMEs

> Built for the IIT Hyderabad National AI/ML Hackathon 2026 — Top 10 Finish out of 7,700+ participants

## Overview
IntelliCredit is an end-to-end credit analysis pipeline that reads raw financial documents (Annual Reports, Bank Statements, GST Filings) uploaded by Indian MSMEs and NBFCs, extracts key financial metrics, and generates a structured credit health dashboard.

## Features
- Multi-format document ingestion: PDF (bordered + borderless tables), CSV, Excel, DOCX
- OCR fallback for scanned documents with image preprocessing
- AI-powered metric extraction via Claude API (Anthropic)
- Offline fallback engines: Regex Analyzer + Derived Metrics Engine
- Supports Indian financial format: lakh/crore unit normalization, parentheses negatives
- Computes: Revenue, PAT, EBITDA, Net Worth, Total Debt, D/E Ratio, DSCR
- Estimation mode from raw Bank Statement and GSTR-3B data when no annual report is available

## Project Structure

```
intellicredit/
├── app.py                  # Main application entry point
├── core/
│   ├── data_ingestor.py    # Multi-format document parser (PDF/CSV/Excel/DOCX)
│   └── ai_analyzer.py      # Financial metrics extractor + derived metrics engine
├── static/                 # Frontend assets (if applicable)
├── templates/              # HTML templates (if applicable)
├── docs/                   # Reference documents and additional notes
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── .gitignore
```

## Tech Stack
- Python 3.10+
- pdfplumber, PyMuPDF (fitz), pytesseract — PDF parsing
- pandas — structured data handling
- Anthropic Claude API — AI-powered extraction
- XGBoost + SHAP — credit scoring and explainability
- Pillow — OCR image preprocessing

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/HarshApurva/intellicredit.git
cd intellicredit
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Add your Anthropic API key inside .env
```

### 5. Run the application
```bash
python app.py
```

## Environment Variables
| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic Claude API key |
| `DEBUG` | Set to `True` for verbose logging |

## How It Works
1. User uploads financial documents (Annual Report PDF, Bank Statement CSV, GSTR-3B)
2. `DataIngestor` routes each file to the correct parser based on file type
3. Extracted text and tables are passed to `FinancialMetricsExtractor`
4. If Claude API is available: Claude agent extracts metrics via structured JSON output
5. If Claude API is unavailable: Offline regex engine + derived metrics estimation kicks in
6. Dashboard displays: Revenue, PAT, EBITDA, Net Worth, Total Debt, D/E Ratio, DSCR

## Team
Built by Team SPB for the IIT Hyderabad National AI/ML Hackathon, March 2026.

## License
MIT License
