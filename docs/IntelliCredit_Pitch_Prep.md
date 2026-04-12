# IntelliCredit - Hackathon Pitch Preparation Document
## IIT Hyderabad | Final Round - Offline Presentation | 22 March 2026

---
## 1. PROBLEM STATEMENT

### The Challenge
In Indian corporate lending, credit managers face a **"Data Paradox"** - overwhelmed by data yet taking weeks to process a single loan application. The current process requires stitching together:

- **Structured Data**: GST filings, ITRs, Bank Statements
- **Unstructured Data**: Annual Reports, Financial Statements, Board Minutes, Rating Reports
- **External Intelligence**: News, MCA filings, Legal disputes (e-Courts)
- **Primary Insights**: Factory site visits, Management interviews

### What Was Asked
Build an **AI-powered Credit Decisioning Engine** that automates end-to-end preparation of a **Comprehensive Credit Appraisal Memo (CAM)** with three pillars:

| Pillar | Requirement | Our Module |
|--------|------------|------------|
| **1. Data Ingestor** | Multi-format parsing, GST vs Bank cross-verification | `data_ingestor.py`, `claude_pdf_processor.py`, `ai_analyzer.py`, `cross_verifier.py` |
| **2. Research Agent** | Web crawling, news/legal/regulatory scanning, qualitative input portal | `research_agent.py`, `nlp_engine.py` |
| **3. Recommendation Engine** | CAM generation, explainable scoring, loan amount & rate suggestion | `scoring_engine.py`, `credit_analyzer.py`, `credit_risk_model.py`, `cam_generator.py` |

### Evaluation Criteria
1. **Extraction Accuracy** - How well we extract from messy, scanned Indian PDFs
2. **Research Depth** - Finding relevant local news/regulatory filings
3. **Explainability** - Can AI "walk the judge through" its logic
4. **Indian Context Sensitivity** - GSTR-2A vs 3B, NBFC nuances, CIBIL

---

## 2. PROPOSED SOLUTION & METHODOLOGY

### Architecture Overview

```
PDF/Excel Upload --> Data Ingestor --> Claude AI PDF Processor
                                   --> Regex-based Extraction Engine
                                   --> GST/Bank Statement Parser
                         |
                         v
                    Cross-Verifier (GST vs Bank Statement Fraud Detection)
                         |
                         v
                    Research Agent (DuckDuckGo/Google Web Crawling)
                         |
                         v
                    NLP Engine (Sentiment + Risk Signal Extraction)
                         |
                         v
                    Credit Analyzer (Entity Classification + Ratio Computation)
                         |
                         v
                    Scoring Engine (Five Cs Model + XGBoost ML)
                         |
                         v
                    CAM Generator (Professional Word/PDF Output)
                         |
                         v
                    Interactive Dashboard (Real-time Visualization)
```

### The 8-Step Pipeline (in `app.py`)

| Step | Name | Module | What It Does |
|------|------|--------|-------------|
| 1 | **Data Ingestion** | `data_ingestor.py` | Parses PDFs (PyMuPDF + pdfplumber + OCR fallback), Excel/CSV |
| 2 | **AI Financial Extraction** | `claude_pdf_processor.py` + `ai_analyzer.py` | Extracts 30+ financial metrics using Claude API + regex engine |
| 3 | **Cross-Verification** | `cross_verifier.py` | GST vs Bank Statement reconciliation, circular trading detection |
| 4 | **Secondary Research** | `research_agent.py` | Web crawls for news, legal cases, MCA filings, regulatory actions |
| 5 | **NLP Analysis** | `nlp_engine.py` | Sentiment analysis, risk signal extraction, entity recognition |
| 6 | **ML Risk Prediction** | `credit_risk_model.py` | XGBoost classifier + SHAP explainability |
| 7 | **Credit Analysis** | `credit_analyzer.py` + `scoring_engine.py` | Entity classification, ratio computation, Five Cs scoring |
| 8 | **CAM Generation** | `cam_generator.py` | Professional Credit Appraisal Memo in Word/PDF |

---

## 3. WHAT CALCULATIONS WE PERFORM

### 3.1 Financial Metric Extraction (from PDFs)

| Metric | Extraction Method |
|--------|------------------|
| **Revenue** | Regex: "Total revenue from operations", "Total income" from P&L |
| **PAT** | Regex: "Owners of the company" from Consolidated P&L section (NOT auditor's report) |
| **Net Worth** | Regex: "Equity attributable to owners" from Consolidated Balance Sheet; fallback: Total Assets - Total Debt |
| **Total Debt** | Component sum: Debt Securities + Borrowings (other than debt securities) + Subordinated Liabilities |
| **EBITDA** | Regex extraction; for NBFCs: computed as PPOP = Revenue - Finance Costs - Employee - Other Exp - Depreciation |
| **Interest Expense** | Regex from P&L Expenses section: "Finance costs" |
| **Operating Cash Flow** | Regex: "Net cash from operating activities" with bracket-negative handling |
| **Current Assets/Liabilities** | Regex from Balance Sheet |
| **Total Assets** | Regex: "Total Assets" with prior year extraction for ROA computation |
| **NII, GNPA, NNPA, CAR, NIM** | Percentage extraction for NBFCs |
| **ROA** | PAT / Average Total Assets × 100 (uses current + prior year average) |
| **ROE** | PAT / Average Net Worth × 100 (uses current + prior year average) |

### 3.2 Unit Detection & Normalization

```
Step 1: Detect unit from document header (Lakhs/Crores/Millions)
Step 2: Extract ALL raw numbers WITHOUT any unit math
Step 3: Apply single divisor ONCE at the end

Divisor Table:
  - Lakhs  → ÷ 100 → Crores
  - Millions → ÷ 10 → Crores
  - Crores → ÷ 1 (no conversion)
```

### 3.3 Computed Credit Ratios (15 Ratios)

| Ratio | Formula | Interpretation |
|-------|---------|----------------|
| **Debt-to-Equity (D/E)** | Total Debt / Net Worth | < 2.0 is healthy |
| **Interest Coverage (ICR)** | EBITDA / Interest Expense | > 3.0 is safe |
| **DSCR** | (PAT + Depreciation + Interest) / (Interest + Principal) | > 1.5 is comfortable |
| **Current Ratio** | Current Assets / Current Liabilities | > 1.5 is ideal |
| **EBITDA Margin** | EBITDA / Revenue × 100 | Industry-dependent |
| **PAT Margin** | PAT / Revenue × 100 | Higher is better |
| **Revenue Growth** | (Current Revenue - Prior Revenue) / Prior Revenue × 100 | Always calculated algebraically |
| **PAT Growth** | Same formula as above | Year-on-year |
| **ROA** | PAT / Avg Total Assets × 100 | >2% for NBFCs is good |
| **ROE** | PAT / Avg Net Worth × 100 | >15% is strong |
| **NIM (NBFCs)** | Net Interest Margin | >3% is healthy |
| **GNPA Ratio** | Gross NPA / Total Advances × 100 | <3% is acceptable |
| **NNPA Ratio** | Net NPA / Total Advances × 100 | <1.5% is good |
| **CRAR/CAR** | Capital Adequacy Ratio | >15% required by RBI |
| **Cost of Funds** | Interest Expense / Total Debt × 100 | Lower is better |

### 3.4 Cross-Verification Calculations

| Check | How It Works |
|-------|-------------|
| **Revenue Reconciliation** | Compare GST-reported revenue vs bank credit entries; flag if >10% variance |
| **Circular Trading Detection** | Find matching credit-debit amounts >₹1L in bank statements (round-tripping) |
| **Revenue Inflation** | Coefficient of variation analysis on monthly GST revenue; flag if CV >0.5 |
| **Cash Flow Consistency** | Compare total inflows vs outflows; flag if outflow ratio >0.95 |
| **GSTR-2A vs GSTR-3B Mismatch** | Compare input tax credit claimed vs auto-populated; flag if >10% variance |

### 3.5 Five Cs Scoring Model

| C | Weight | Key Inputs |
|---|--------|------------|
| **Character** (25%) | Media sentiment score, risk signal count, legal issues, promoter reputation |
| **Capacity** (25%) | DSCR, ICR, revenue growth, PAT margin, operating cash flow |
| **Capital** (20%) | D/E ratio, net worth, total assets, ROE/ROA |
| **Collateral** (15%) | Current ratio, asset coverage, tangible assets |
| **Conditions** (15%) | Industry outlook sentiment, regulatory risk, sector growth |

**Final Score** = Σ(C_score × C_weight) - Cross-Verification Penalty ± Qualitative Adjustment

### 3.6 Loan Recommendation Logic

```python
if score >= 75:  APPROVE, rate = base_rate + 50-100 bps
if score >= 60:  APPROVE with conditions, rate = base_rate + 100-200 bps
if score >= 45:  REFER to committee, rate = base_rate + 200-350 bps
if score < 45:   REJECT

Max Loan = Net Worth × multiplier (based on risk grade)
```

---

## 4. AI/ML MODELS USED & WHY

### 4.1 Models We Use

| Model | Purpose | Why This Model |
|-------|---------|---------------|
| **Claude 3.5 Sonnet** (Anthropic) | Primary PDF extraction for complex documents | Best-in-class document understanding; handles messy Indian PDFs with tables, multi-column layouts; structured JSON output; 200K context window for full annual reports |
| **GPT-4o** (OpenAI) | Narrative generation, CAM analysis, qualitative insights | Superior narrative quality for professional CAM documents; understands Indian financial context |
| **XGBoost Classifier** | Credit risk binary classification (Default/No Default) | Industry-standard for tabular financial data; handles missing values natively; fast inference; proven in banking credit scoring |
| **SHAP** (SHapley Additive exPlanations) | Model explainability | Provides feature-level explanations for every prediction; shows WHY a loan was approved/rejected |
| **Custom NLP Lexicon** | Sentiment analysis, risk signal extraction | Tailored 100+ keyword Indian credit-context lexicon covering NCLT, SFIO, RBI penalties; faster than LLM for batch processing |
| **Regex Pattern Engine** | Financial data extraction from PDF text | Unit-aware, handles bracket negatives (Indian accounting format), multi-column year extraction |

### 4.2 Why NOT These Models

| Model | Why We Didn't Use It |
|-------|---------------------|
| **FinBERT/BERT** | Overkill for our keyword-based credit sentiment; our custom lexicon is faster and Indian-context specific |
| **Random Forest** | XGBoost consistently outperforms RF on tabular financial data with missing values |
| **GPT-4 Vision** | Claude 3.5 Sonnet is more reliable for structured extraction from Indian PDFs; Claude's system prompts enforce JSON schema better |
| **LLaMA/Open-source LLMs** | Needs GPU infrastructure; latency too high for real-time analysis; weaker at structured extraction |
| **Traditional OCR (Tesseract only)** | We use PyMuPDF + pdfplumber which handle native PDFs better; Tesseract is our fallback for scanned pages |
| **Deep Learning for NER** | Our regex-based entity extraction is more precise for Indian financial entities (₹ amounts, GST numbers, credit ratings) |

### 4.3 Dual-Track Extraction (Unique Approach)

```
PDF Upload
    ├── Track 1: Claude API (structured JSON extraction with schema)
    │   - 30+ financial fields in one call
    │   - Handles messy PDFs end-to-end
    │   - Costs ≈ $0.03/page
    │
    └── Track 2: Regex Engine (ai_analyzer.py)
        - 10 specialized extraction functions
        - Unit detection + divisor normalization
        - Zero API cost
        - Deterministic, reproducible

Result: Best of both tracks merged
```

---

## 5. HOW OUR MODEL IS DIFFERENT

### 5.1 Key Differentiators

| Feature | Traditional Credit Tools | IntelliCredit |
|---------|------------------------|---------------|
| **Processing Time** | 2-3 weeks per application | **< 5 minutes** end-to-end |
| **Data Sources** | Manual collection | **Automated multi-source** (PDF + GST + Bank + Web) |
| **Fraud Detection** | Post-facto audits | **Real-time** circular trading + GST mismatch detection |
| **NBFC Support** | One-size-fits-all | **Dedicated NBFC pipeline** (PPOP, NII, GNPA, CRAR) |
| **Explainability** | Black box scores | **SHAP + Five Cs breakdown** with factor-level reasoning |
| **Research** | Manual Google searches | **Automated web crawling** for news, legal, MCA, regulatory |
| **CAM Generation** | Manual Word document | **Auto-generated** professional Word/PDF CAM |
| **Indian Context** | Western models adapted | **Built for India** - Lakhs/Crores, GSTR-2A/3B, NCLT, RBI |

### 5.2 Indian Context Sensitivity (Evaluation Criteria #4)

1. **Unit Handling**: Detects Lakhs/Crores/Millions from PDF headers; normalizes everything to Crores
2. **GSTR-2A vs 3B**: Specific cross-verification check for ITC mismatch
3. **NBFC Classification**: Auto-detects NBFCs from keywords (NII, GNPA, AUM, CRAR) and adapts all metrics
4. **Indian Accounting Format**: Handles bracket notation for negatives: `(22,489.55)` = -22489.55
5. **Indian Credit Ratings**: Extracts CRISIL, ICRA, CARE, India Ratings, Brickwork, Acuite ratings
6. **Indian Legal Context**: Monitors NCLT, SFIO, CBI, ED, SEBI, RBI actions
7. **Indian Financial Terms**: PPOP (Pre-Provision Operating Profit), NII, NIM, PCR

### 5.3 Sanity Checks (Extraction Accuracy)

Our system performs **10+ automated sanity checks**:
- PAT must be < Revenue (swap detection)
- PAT Margin must be < 150%
- GNPA must be > NNPA
- CRAR must be > 10% (regulatory minimum)
- ROA != ROE (impossible for leveraged firms)
- Finance cost must be 3-25% of debt
- Total Debt must be > 5% of Total Assets
- Revenue growth calculated algebraically (never extracted as text)

---

## 6. COMPLETE PIPELINE WALKTHROUGH

### Step-by-Step Flow

```
USER UPLOADS FILES (PDF Annual Report + GST Excel + Bank CSV)
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1: DATA INGESTION (data_ingestor.py)          │
│  ─────────────────────────────────────────          │
│  • PyMuPDF extracts text from PDF pages             │
│  • pdfplumber extracts tables                       │
│  • OCR fallback for scanned pages                   │
│  • Pandas parses Excel/CSV for GST & Bank data      │
│  • Document classification (annual report, legal,   │
│    bank stmt, GST filing)                           │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2: AI FINANCIAL EXTRACTION                    │
│  ─────────────────────────────────                  │
│  Track A: Claude API (claude_pdf_processor.py)      │
│    • Sends full PDF text to Claude 3.5 Sonnet       │
│    • Structured JSON schema for 30+ metrics         │
│    • Indian-context extraction rules in prompt      │
│                                                     │
│  Track B: Regex Engine (ai_analyzer.py)             │
│    • Unit detection (Lakhs/Crores/Millions)         │
│    • Revenue from "Total revenue from operations"   │
│    • PAT from Consolidated P&L section only         │
│    • Net Worth from "Equity attributable to owners" │
│    • Total Debt = Debt Securities + Borrowings +    │
│      Subordinated Liabilities                       │
│    • 10+ specialized regex extractors               │
│    • Bracket-negative handling                      │
│    • Prior year extraction for growth calculation   │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3: CROSS-VERIFICATION (cross_verifier.py)     │
│  ──────────────────────────────                     │
│  • GST revenue vs Bank credits reconciliation       │
│  • Circular trading detection (matching amounts)    │
│  • Revenue inflation analysis (CV > 0.5 flag)       │
│  • Cash flow consistency check                      │
│  • GSTR-2A vs GSTR-3B ITC mismatch                 │
│  • Outputs reconciliation score (0-100)             │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4: RESEARCH AGENT (research_agent.py)         │
│  ─────────────────────────────                      │
│  • DuckDuckGo/Google web search                     │
│  • News: company + promoter news                    │
│  • Legal: NCLT, litigation, court cases             │
│  • MCA: Ministry of Corporate Affairs filings       │
│  • Sector: Industry outlook, RBI regulations        │
│  • Regulatory: SEBI, RBI actions/circulars          │
│  • Qualitative inputs from Credit Officer portal    │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5: NLP ANALYSIS (nlp_engine.py)               │
│  ────────────────────────                           │
│  • Sentiment analysis (100+ Indian credit keywords) │
│  • Risk signal extraction (6 categories: financial, │
│    governance, legal, regulatory, fraud, operational)│
│  • Entity extraction (INR amounts, dates, ratings)  │
│  • Batch sentiment across all research articles     │
│  • Critical keyword threshold for fraud signals     │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 6: ML RISK PREDICTION (credit_risk_model.py)  │
│  ─────────────────────────────                      │
│  • XGBoost classifier (14 features)                 │
│  • Features: revenue_growth, ebitda_margin,         │
│    pat_margin, D/E, current_ratio, DSCR, ICR,       │
│    promoter_holding, years_in_business,             │
│    sentiment_score, litigation_count, CV score,     │
│    industry_risk_score                              │
│  • SHAP explainability for every prediction         │
│  • Can train from real PDFs or synthetic data       │
│  • Saved model: credit_risk_xgb.pkl                 │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 7: CREDIT ANALYSIS & SCORING                  │
│  ─────────────────────────────────                  │
│  credit_analyzer.py:                                │
│    • Entity classification (NBFC vs Non-NBFC)       │
│    • Input extraction with fallback logic           │
│    • 15 credit ratio computations                   │
│    • Ratio interpretation & benchmarking            │
│    • Weighted scoring across all ratios             │
│    • Anomaly detection (10+ flags)                  │
│                                                     │
│  scoring_engine.py:                                 │
│    • Five Cs scoring (Character 25%, Capacity 25%,  │
│      Capital 20%, Collateral 15%, Conditions 15%)   │
│    • Cross-verification penalty applied             │
│    • Qualitative adjustment from officer inputs     │
│    • Early warning signal detection                 │
│    • Risk grade assignment (AAA to D)               │
│    • Loan recommendation with rate & amount         │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  STEP 8: CAM GENERATION (cam_generator.py)          │
│  ──────────────────────────                         │
│  Professional Credit Appraisal Memo with:           │
│  1. Executive Summary with scorecard table          │
│  2. Company Overview                                │
│  3. Promoter Background                             │
│  4. Financial Analysis (metrics table)              │
│  5. Five Cs Assessment (score + narrative)          │
│  6. Cross-Verification Results                      │
│  7. Secondary Research Findings                     │
│  8. Primary Due Diligence Notes                     │
│  9. Risk Assessment Matrix                          │
│  10. Final Recommendation (APPROVE/REFER/REJECT)    │
│                                                     │
│  Output: Word (.docx) + PDF                         │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  INTERACTIVE DASHBOARD (app.js + Flask)             │
│  ──────────────────────────────────                 │
│  • Real-time pipeline progress tracking             │
│  • Financial metrics cards with charts              │
│  • Credit Analysis tab with ratio breakdowns        │
│  • Cross-verification visualization                 │
│  • Research findings with sentiment indicators      │
│  • SHAP waterfall chart for ML explainability       │
│  • One-click CAM download (Word/PDF)                │
└─────────────────────────────────────────────────────┘
```

---

## 7. IMPLEMENTATION FEASIBILITY & IMPACT

### 7.1 Technical Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.x, Flask |
| **AI/LLM** | Claude 3.5 Sonnet (Anthropic), GPT-4o (OpenAI) |
| **ML** | XGBoost, SHAP, scikit-learn, NumPy, Pandas |
| **PDF Processing** | PyMuPDF (fitz), pdfplumber, Tesseract OCR |
| **NLP** | Custom Indian credit lexicon (100+ keywords) |
| **Web Scraping** | DuckDuckGo API, BeautifulSoup, Requests |
| **Document Generation** | python-docx (Word), ReportLab (PDF) |
| **Frontend** | HTML5, JavaScript, Chart.js |
| **Data Integration** | Databricks connector ready |

### 7.2 Deployment Feasibility

- **Cloud-Ready**: Can deploy on AWS/Azure/GCP with minimal changes
- **API-Based**: RESTful Flask API, easy to integrate with existing LOS/LMS systems
- **Scalable**: Can process multiple applications concurrently
- **Databricks Integration**: Built-in connector for enterprise data lake
- **Cost**: ~$0.05-0.10 per credit application (API costs)

### 7.3 Impact Metrics

| Metric | Current (Manual) | With IntelliCredit |
|--------|-----------------|-------------------|
| **Processing Time** | 2-3 weeks | **< 5 minutes** |
| **Cost per Application** | ₹15,000-25,000 | **₹5-10** (API costs) |
| **Fraud Detection** | Post-facto | **Real-time** |
| **Consistency** | Human-dependent | **100% standardized** |
| **Coverage** | 8-10 data points | **30+ metrics + web research** |
| **Explainability** | Subjective notes | **SHAP + Five Cs + Scoring Factors** |

---

## 8. CODE ARCHITECTURE SUMMARY

### File Structure
```
IntelliCredit/
├── app.py                          # Flask backend, 8-step pipeline orchestrator
├── config.py                       # API keys, settings
├── core/
│   ├── data_ingestor.py            # PDF/Excel/CSV parsing (504 lines)
│   ├── claude_pdf_processor.py     # Claude API PDF extraction (307 lines)
│   ├── ai_analyzer.py              # Regex extraction + LLM interface (1116 lines)
│   ├── cross_verifier.py           # GST vs Bank fraud detection (330 lines)
│   ├── research_agent.py           # Web crawling for intelligence (386 lines)
│   ├── nlp_engine.py               # Sentiment + risk signals (357 lines)
│   ├── credit_analyzer.py          # Entity classification + ratios (781 lines)
│   ├── scoring_engine.py           # Five Cs scoring model (472 lines)
│   ├── cam_generator.py            # Word/PDF CAM generation (540 lines)
│   ├── databricks_connector.py     # Enterprise data lake connector
│   └── pdf_training_extractor.py   # ML training data from PDFs
├── models/
│   ├── credit_risk_model.py        # XGBoost + SHAP (310 lines)
│   ├── credit_risk_xgb.pkl         # Trained model weights
│   └── sample_data.py              # Synthetic training data generator
├── static/js/app.js                # Interactive dashboard (1188 lines)
├── templates/index.html            # Frontend template
└── Total: ~6,500+ lines of code
```

---

## 9. PITCH TALKING POINTS

### Opening (30 sec)
> "Credit managers spend 2-3 weeks per loan application stitching together data from 10+ sources. IntelliCredit does it in under 5 minutes with AI - and catches fraud that humans miss."

### Demo Flow (suggested)
1. Upload an NBFC Annual Report PDF → Show real-time extraction
2. Point out Net Worth, PAT, Revenue auto-extracted with unit normalization
3. Show Cross-Verification tab → Circular trading detection
4. Show Research tab → Live web-crawled news and legal findings
5. Show Credit Analysis → Five Cs breakdown with SHAP explanation
6. Download CAM → Professional 10-section document auto-generated

### Key Differentiators to Emphasize
1. **Dual-track extraction** (Claude + Regex) - accuracy + reliability
2. **NBFC-aware** - not just generic corporate analysis
3. **Fraud detection** built into the pipeline (circular trading, GST mismatch)
4. **Explainable** - every decision has SHAP + Five Cs + factor-level reasoning
5. **Indian context** - Lakhs/Crores, GSTR, NCLT, bracket negatives
6. **End-to-end automation** - from PDF upload to CAM download in one click

### Handling Tough Questions
- **"How accurate is extraction?"** → We have 10+ sanity checks: PAT < Revenue, GNPA > NNPA, ROA ≠ ROE, etc. Dual-track extraction (Claude + Regex) provides cross-validation.
- **"What about scanned PDFs?"** → PyMuPDF primary + OCR fallback for scanned pages.
- **"Is the ML model trained on real data?"** → Yes, `train_from_pdfs()` extracts features from real annual reports, augments with synthetic data centered on real distributions.
- **"How is this different from CIBIL/bureau scores?"** → We analyze unstructured data (annual reports, news, legal) that bureau scores miss. We also perform GST-Bank cross-verification for fraud detection.

---

*Document prepared for Team SPB | IntelliCredit | IIT Hyderabad Hackathon 2026*
