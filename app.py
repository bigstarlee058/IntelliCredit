"""
Intelli-Credit: AI-Powered Credit Decisioning Engine
======================================================
Flask application entry point.
Developed by Team SPB
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime

from flask import (
    Flask, render_template, request, jsonify, send_file, Response
)
from flask_cors import CORS

from config import Config

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("intelli-credit")

# ── Flask App ──
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
Config.ensure_dirs()

# ── Global State ──
pipeline_state = {
    "status": "idle",
    "step": "",
    "progress": 0,
    "results": {},
    "errors": [],
}


# ═══════════════════════════════════════════════════════════════════
#  ROUTES - PAGES
# ═══════════════════════════════════════════════════════════════════

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


# ═══════════════════════════════════════════════════════════════════
#  API - FILE UPLOAD
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/upload", methods=["POST"])
def upload_files():
    """Upload company documents for analysis."""
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    uploaded = []

    # Clear old uploads so stale files don't contaminate new analysis
    for old_file in os.listdir(Config.UPLOAD_FOLDER):
        old_path = os.path.join(Config.UPLOAD_FOLDER, old_file)
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    for file in files:
        if file.filename and Config.allowed_file(file.filename):
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            uploaded.append({"filename": file.filename, "saved_as": filename, "path": filepath})
        else:
            uploaded.append({"filename": file.filename, "error": "Invalid file type"})

    return jsonify({"uploaded": uploaded, "count": len([u for u in uploaded if "path" in u])})


# ═══════════════════════════════════════════════════════════════════
#  METRIC ENRICHMENT HELPER
# ═══════════════════════════════════════════════════════════════════

def _safe_metric_val(metrics, key):
    """Extract numeric value from a metric, handling nested {value: X} dicts."""
    v = metrics.get(key)
    if v is None:
        return None
    if isinstance(v, dict):
        inner = v.get("value")
        if inner is None or inner == 0:
            return None
        return inner
    if isinstance(v, (int, float)) and v != 0:
        return v
    return None


def _enrich_metrics_with_fallbacks(metrics):
    """
    Enrich financial_metrics dict in-place with computed fallback values
    for Net Worth, PAT, and D/E ratio when Claude returns null.
    """
    # --- Net Worth fallback ---
    nw = _safe_metric_val(metrics, "net_worth")
    if nw is None:
        # Fallback 1: tangible_net_worth
        nw = _safe_metric_val(metrics, "tangible_net_worth")
        if nw:
            metrics["net_worth"] = {"value": nw, "unit": "Cr"}
            logger.info(f"Enriched Net Worth from tangible_net_worth: {nw}")

    if nw is None:
        # Fallback 2: total_assets - total_debt
        ta = _safe_metric_val(metrics, "total_assets")
        td = _safe_metric_val(metrics, "total_debt")
        if ta and td:
            nw = round(ta - td, 2)
            metrics["net_worth"] = {"value": nw, "unit": "Cr"}
            logger.info(f"Enriched Net Worth from total_assets({ta}) - total_debt({td}) = {nw}")

    # --- PAT fallback ---
    pat = _safe_metric_val(metrics, "pat")
    if pat is None:
        pat_obj = metrics.get("pat")
        rev = _safe_metric_val(metrics, "revenue")
        if isinstance(pat_obj, dict) and pat_obj.get("margin_pct") and rev:
            margin = pat_obj["margin_pct"]
            pat = round(rev * margin / 100, 2)
            metrics["pat"] = {"value": pat, "unit": "Cr", "margin_pct": margin}
            logger.info(f"Enriched PAT from revenue({rev}) * margin({margin}%) = {pat}")

    # --- D/E ratio fallback ---
    de = metrics.get("debt_equity_ratio")
    if not de or de == 0:
        td = _safe_metric_val(metrics, "total_debt")
        nw_now = _safe_metric_val(metrics, "net_worth")
        if td and nw_now and nw_now > 0:
            metrics["debt_equity_ratio"] = round(td / nw_now, 2)
            logger.info(f"Enriched D/E ratio: {td}/{nw_now} = {metrics['debt_equity_ratio']}")


# ═══════════════════════════════════════════════════════════════════
#  API - ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/analyze", methods=["POST"])
def run_analysis():
    """Run the full credit analysis pipeline."""
    global pipeline_state

    try:
        data = request.json or {}
        company_name = data.get("company_name", "")
        promoter_names = data.get("promoter_names", [])
        use_sample = data.get("use_sample", False)
        sample_type = data.get("sample_type", "healthy")

        pipeline_state = {
            "status": "running",
            "step": "Initializing pipeline...",
            "progress": 5,
            "results": {},
            "errors": [],
        }

        # ── Step 1: Data Ingestion ──
        pipeline_state["step"] = "Ingesting documents..."
        pipeline_state["progress"] = 10

        if use_sample:
            from models.sample_data import generate_company_profile, generate_gst_data, generate_bank_statement
            financial_metrics = generate_company_profile(sample_type)
            company_name = financial_metrics.get("company_name", company_name)

            gst_df = generate_gst_data(sample_type)
            bank_df = generate_bank_statement(sample_type)
            gst_data = {
                "data_type": "gst_filing",
                "preview": gst_df.to_dict(orient="records"),
                "analysis": {"type": "GST Filing Analysis", "total_taxable_value": float(gst_df["Taxable_Value_Lakhs"].sum())},
            }
            bank_data = {
                "data_type": "bank_statement",
                "preview": bank_df.to_dict(orient="records"),
                "analysis": {
                    "type": "Bank Statement Analysis",
                    "total_credits": float(bank_df["Credit"].sum()),
                    "total_debits": float(bank_df["Debit"].sum()),
                },
            }
            ingested_docs = [gst_data, bank_data]
        else:
            from core.data_ingestor import ingest_multiple
            upload_dir = Config.UPLOAD_FOLDER
            files = [
                os.path.join(upload_dir, f)
                for f in os.listdir(upload_dir)
                if os.path.isfile(os.path.join(upload_dir, f))
            ]
            ingested_docs = ingest_multiple(files) if files else []

            # Extract financial metrics - Claude first, regex as fallback
            financial_metrics = {}
            user_provided_name = company_name  # Preserve what the user typed

            if ingested_docs:
                # ── Try Claude PDF extraction first (best quality) ──
                try:
                    from core.claude_pdf_processor import extract_from_pdf, is_available
                    if is_available():
                        for doc in ingested_docs:
                            # Find the saved file path for this doc (PDFs only)
                            doc_filename = doc.get("filename", "")
                            if not doc_filename.lower().endswith(".pdf"):
                                continue
                            # Find matching file in upload dir
                            for f in files:
                                if os.path.basename(f).endswith(doc_filename) or doc_filename in os.path.basename(f):
                                    pipeline_state["step"] = f"Extracting financials from {doc_filename} via Claude..."
                                    claude_metrics = extract_from_pdf(f)
                                    if claude_metrics and not claude_metrics.get("error"):
                                        financial_metrics = claude_metrics
                                        logger.info(f"Claude extraction succeeded for {doc_filename}")
                                        if not user_provided_name:
                                            ai_name = claude_metrics.get("company_name", "")
                                            reject_words = ["sample", "statement", "summary", "template",
                                                            "financial_", "large", "small", "dataset",
                                                            "uploaded", "unknown"]
                                            if ai_name and not any(w in ai_name.lower() for w in reject_words):
                                                company_name = ai_name
                                        break
                            if financial_metrics:
                                break  # Got metrics from Claude, stop searching
                except Exception as e:
                    logger.warning(f"Claude PDF extraction failed, falling back to regex: {e}")

                # ── Fallback: regex on extracted text ──
                if not financial_metrics:
                    for doc in ingested_docs:
                        if doc.get("text"):
                            try:
                                from core.ai_analyzer import extract_financial_metrics
                                financial_metrics = extract_financial_metrics(doc["text"])
                                if not financial_metrics.get("error"):
                                    if not user_provided_name:
                                        ai_name = financial_metrics.get("company_name", "")
                                        reject_words = ["sample", "statement", "summary", "template",
                                                        "financial_", "large", "small", "dataset",
                                                        "uploaded", "unknown"]
                                        if ai_name and not any(w in ai_name.lower() for w in reject_words):
                                            company_name = ai_name
                                    break
                            except Exception as e:
                                logger.warning(f"Regex extraction failed: {e}")


            gst_data = next((d for d in ingested_docs if d.get("data_type") == "gst_filing"), {})
            bank_data = next((d for d in ingested_docs if d.get("data_type") == "bank_statement"), {})

            # If no PDF financials found, derive estimates from bank statement
            if not financial_metrics and bank_data.get("analysis"):
                ba = bank_data["analysis"]
                total_credits = ba.get("total_credits", 0)
                total_debits = ba.get("total_debits", 0)
                avg_balance = ba.get("avg_balance", 0)
                net_flow = ba.get("net_cash_flow", total_credits - total_debits)

                # Convert to Crores for display
                revenue_cr = round(total_credits / 1e7, 2)
                expenses_cr = round(total_debits / 1e7, 2)
                pat_cr = round(net_flow / 1e7, 2)
                ebitda_cr = round(pat_cr * 1.3, 2)  # Approximate EBITDA
                ebitda_margin = round((ebitda_cr / revenue_cr * 100), 1) if revenue_cr else 0
                pat_margin = round((pat_cr / revenue_cr * 100), 1) if revenue_cr else 0
                revenue_growth = 8.0  # Default estimate

                financial_metrics = {
                    "company_name": company_name or "Uploaded Company",
                    "financial_year": "2024",
                    "revenue": {"value": revenue_cr, "unit": "Cr", "growth_pct": revenue_growth},
                    "ebitda": {"value": ebitda_cr, "unit": "Cr", "margin_pct": ebitda_margin},
                    "pat": {"value": pat_cr, "unit": "Cr", "margin_pct": pat_margin},
                    "total_debt": {"value": round(expenses_cr * 0.15, 2), "unit": "Cr"},
                    "net_worth": {"value": round(avg_balance / 1e7, 2), "unit": "Cr"},
                    "debt_equity_ratio": round(expenses_cr * 0.15 / max(avg_balance / 1e7, 0.01), 2),
                    "current_ratio": round(total_credits / max(total_debits, 1), 2),
                    "interest_coverage_ratio": round(ebitda_cr / max(expenses_cr * 0.02, 0.01), 2),
                    "dscr": round(ebitda_cr / max(expenses_cr * 0.03, 0.01), 2),
                    "cash_flow_from_operations": {"value": pat_cr, "unit": "Cr"},
                    "total_assets": {"value": round(revenue_cr * 0.8, 2), "unit": "Cr"},
                    "tangible_net_worth": {"value": round(avg_balance / 1e7 * 0.9, 2), "unit": "Cr"},
                    "working_capital": {"value": round(net_flow / 1e7, 2), "unit": "Cr"},
                    "debtors_days": 45,
                    "creditors_days": 30,
                    "inventory_days": 20,
                    "promoter_holding_pct": 0,
                    "key_risks": ["Estimated from bank statement only"],
                    "key_strengths": [f"Net positive cash flow of ₹{pat_cr} Cr"],
                    "red_flags": [],
                    "credit_count": ba.get("credit_count", 0),
                    "total_transactions": bank_data.get("row_count", 0),
                    "avg_balance": round(avg_balance, 2),
                    "min_balance": ba.get("min_balance", 0),
                    "max_balance": ba.get("max_balance", 0),
                    "data_source": "bank_statement_derived",
                }

        # ── Post-process: fill in missing metrics via fallback computations ──
        if financial_metrics:
            _enrich_metrics_with_fallbacks(financial_metrics)

        pipeline_state["progress"] = 25
        pipeline_state["results"]["ingestion"] = {
            "company_name": company_name or financial_metrics.get("company_name", "Unknown Company"),
            "documents_processed": len(ingested_docs) if not use_sample else 2,
            "financial_metrics": financial_metrics,
        }

        # ── Step 2: Cross-Verification ──
        pipeline_state["step"] = "Running cross-verification..."
        pipeline_state["progress"] = 35

        from core.cross_verifier import CrossVerifier
        verifier = CrossVerifier()
        if gst_data:
            verifier.load_gst_data(gst_data)
        if bank_data:
            verifier.load_bank_data(bank_data)
        cross_verification = verifier.run_verification()

        pipeline_state["results"]["cross_verification"] = cross_verification
        pipeline_state["progress"] = 45

        # ── Step 3: Research Agent ──
        pipeline_state["step"] = "Running secondary research..."
        pipeline_state["progress"] = 50

        research_results = {"findings": {"news": [], "legal": [], "mca": {}, "sector": [], "regulatory": []}}
        if company_name:
            try:
                from core.research_agent import ResearchAgent
                agent = ResearchAgent(company_name, promoter_names)
                research_results = agent.run_full_research()
            except Exception as e:
                logger.warning(f"Research agent failed: {e}")
                pipeline_state["errors"].append(f"Research: {str(e)}")

        pipeline_state["results"]["research"] = research_results
        pipeline_state["progress"] = 65

        # ── Step 4: NLP Analysis ──
        pipeline_state["step"] = "Analyzing sentiment & risk signals..."
        pipeline_state["progress"] = 70

        from core.nlp_engine import analyze_research_findings
        nlp_results = analyze_research_findings(research_results.get("findings", {}))

        pipeline_state["results"]["nlp"] = nlp_results
        pipeline_state["progress"] = 75

        # ── Step 5: ML Prediction ──
        pipeline_state["step"] = "Running ML credit risk model..."
        pipeline_state["progress"] = 80

        from models.credit_risk_model import CreditRiskModel, prepare_features_from_analysis
        ml_model = CreditRiskModel()
        ml_model.load()

        ml_features = prepare_features_from_analysis(
            financial_metrics, nlp_results, cross_verification, research_results
        )
        ml_prediction = ml_model.predict(ml_features)

        pipeline_state["results"]["ml_prediction"] = ml_prediction
        pipeline_state["progress"] = 85

        # ── Step 6: Five Cs Scoring ──
        pipeline_state["step"] = "Computing Five Cs score..."
        pipeline_state["progress"] = 88

        from core.scoring_engine import FiveCsScorer
        scorer = FiveCsScorer()
        scoring_result = scorer.score(
            financial_data={"metrics": financial_metrics},
            research_data=research_results,
            nlp_data=nlp_results,
            cross_verification=cross_verification,
        )

        pipeline_state["results"]["scoring"] = scoring_result
        pipeline_state["progress"] = 92

        # ── Step 6b: Structured Credit Analysis (CAM) ──
        pipeline_state["step"] = "Running structured credit analysis..."
        try:
            from core.credit_analyzer import CreditAnalyzer
            # Ensure financial_metrics has at least a company name
            fm_for_ca = financial_metrics if financial_metrics else {"company_name": company_name or "Unknown"}
            credit_analysis = CreditAnalyzer.run_full_analysis(fm_for_ca)
            pipeline_state["results"]["credit_analysis"] = credit_analysis
        except Exception as e:
            err_detail = traceback.format_exc()
            logger.warning(f"Credit analysis failed: {err_detail}")
            pipeline_state["errors"].append(f"Credit Analysis: {str(e)}")
            # Still include a stub so the frontend knows what happened
            pipeline_state["results"]["credit_analysis"] = {
                "error": str(e),
                "entity_classification": {"entity_type": "UNKNOWN", "description": f"Classification failed: {str(e)}"},
                "financial_inputs": {"common": {}, "nbfc": {}},
                "credit_ratios": [],
                "credit_scoring": {"final_score": 0, "rating": "Error", "breakdown": []},
                "anomaly_flags": [],
                "company_name": company_name or "Unknown",
                "financial_year": "N/A",
            }
        pipeline_state["progress"] = 94

        # ── Step 7: AI Narrative ──
        pipeline_state["step"] = "Generating AI narrative..."
        pipeline_state["progress"] = 95

        narrative = {}
        try:
            from core.ai_analyzer import generate_credit_narrative
            narrative = generate_credit_narrative({
                "company_name": company_name,
                "financial_metrics": financial_metrics,
                "scoring": scoring_result,
                "cross_verification": cross_verification,
                "research_summary": {
                    "news_sentiment": nlp_results.get("news_sentiment", {}),
                    "risk_level": nlp_results.get("risk_signals", {}).get("risk_level", "N/A"),
                },
                "ml_prediction": ml_prediction,
            })
        except Exception as e:
            logger.warning(f"AI narrative generation failed: {e}")
            pipeline_state["errors"].append(f"AI Narrative: {str(e)}")

        pipeline_state["results"]["narrative"] = narrative

        # ── Databricks Save ──
        try:
            from core.databricks_connector import DatabricksConnector
            db = DatabricksConnector()
            if db.connect():
                db.save_analysis_results(company_name, pipeline_state["results"])
                pipeline_state["results"]["databricks"] = {"status": "saved"}
            else:
                pipeline_state["results"]["databricks"] = {"status": "local_mode"}
        except Exception as e:
            pipeline_state["results"]["databricks"] = {"status": "unavailable", "error": str(e)}

        # ── Complete ──
        pipeline_state["status"] = "complete"
        pipeline_state["step"] = "Analysis complete!"
        pipeline_state["progress"] = 100

        return jsonify(pipeline_state["results"])

    except Exception as e:
        logger.error(f"Pipeline error: {traceback.format_exc()}")
        pipeline_state["status"] = "error"
        pipeline_state["step"] = f"Error: {str(e)}"
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


# ═══════════════════════════════════════════════════════════════════
#  API - STRUCTURED CREDIT ANALYSIS (CAM)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/credit-analysis", methods=["POST"])
def run_credit_analysis():
    """Run structured 5-step credit analysis on existing pipeline results."""
    results = pipeline_state.get("results", {})
    financial_metrics = results.get("ingestion", {}).get("financial_metrics", {})

    if not financial_metrics:
        return jsonify({"error": "No financial metrics available. Run analysis first."}), 400

    try:
        from core.credit_analyzer import CreditAnalyzer
        analysis = CreditAnalyzer.run_full_analysis(financial_metrics)
        pipeline_state["results"]["credit_analysis"] = analysis
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Credit analysis error: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/analyze-pdf-claude", methods=["POST"])
def analyze_pdf_claude():
    """Extract financial metrics from a PDF using Claude's native document understanding."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Send a PDF as 'file'."}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    try:
        # Save temporarily
        filepath = os.path.join(Config.UPLOAD_FOLDER, f"claude_{file.filename}")
        file.save(filepath)

        from core.claude_pdf_processor import extract_from_pdf, is_available
        if not is_available():
            return jsonify({
                "error": "Claude PDF processing is not available. "
                         "Set ANTHROPIC_API_KEY in .env to enable it."
            }), 503

        result = extract_from_pdf(filepath)
        if result is None:
            return jsonify({"error": "Claude extraction failed. Check logs for details."}), 500

        # Also run the credit analysis on the extracted metrics
        from core.credit_analyzer import CreditAnalyzer
        credit_analysis = CreditAnalyzer.run_full_analysis(result)

        return jsonify({
            "financial_metrics": result,
            "credit_analysis": credit_analysis,
        })
    except Exception as e:
        logger.error(f"Claude PDF error: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


# ═══════════════════════════════════════════════════════════════════
#  API - QUALITATIVE INPUT
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/qualitative-input", methods=["POST"])
def add_qualitative_input():
    """Add credit officer qualitative notes."""
    data = request.json
    notes = data.get("notes", "")
    category = data.get("category", "general_observation")
    officer_name = data.get("officer_name", "")

    if not notes:
        return jsonify({"error": "Notes are required"}), 400

    from core.research_agent import QualitativeInputHandler
    handler = QualitativeInputHandler()
    entry = handler.add_input(category, notes, officer_name)

    # Analyze with AI
    current_score = pipeline_state.get("results", {}).get("scoring", {}).get("overall_score", 50)
    try:
        from core.ai_analyzer import analyze_qualitative_input
        analysis = analyze_qualitative_input(notes, current_score)
        entry["ai_analysis"] = analysis
    except Exception as e:
        entry["ai_analysis"] = {"error": str(e)}

    return jsonify(entry)


# ═══════════════════════════════════════════════════════════════════
#  API - CAM GENERATION
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/generate-cam", methods=["POST"])
def generate_cam():
    """Generate Credit Appraisal Memo document."""
    data = request.json or {}
    fmt = data.get("format", "word")  # "word" or "pdf"

    results = pipeline_state.get("results", {})
    if not results:
        return jsonify({"error": "No analysis results available. Run analysis first."}), 400

    company_name = results.get("ingestion", {}).get("company_name", "Company")

    cam_data = {
        "company_name": company_name,
        "financial_metrics": results.get("ingestion", {}).get("financial_metrics", {}),
        "scoring": results.get("scoring", {}),
        "cross_verification": results.get("cross_verification", {}),
        "research_analysis": results.get("nlp", {}),
        "narrative": results.get("narrative", {}),
        "ml_prediction": results.get("ml_prediction", {}),
        "qualitative_data": results.get("qualitative", {}),
    }

    from core.cam_generator import CAMGenerator
    generator = CAMGenerator(cam_data)

    try:
        if fmt == "pdf":
            output_path = generator.generate_pdf()
        else:
            output_path = generator.generate_word()

        return jsonify({
            "status": "generated",
            "format": fmt,
            "filename": os.path.basename(output_path),
            "path": output_path,
        })
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/download-cam/<filename>")
def download_cam(filename):
    """Download generated CAM document."""
    filepath = os.path.join(Config.OUTPUT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


# ═══════════════════════════════════════════════════════════════════
#  API - PDF MODEL TRAINING
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/train-from-pdfs", methods=["POST"])
def train_from_pdfs():
    """Batch-train the ML model from all PDFs in the Data folder."""
    try:
        data = request.json or {}
        data_folder = data.get("data_folder", None)  # Optional custom path

        from models.credit_risk_model import CreditRiskModel
        model = CreditRiskModel()
        model.train_from_pdfs(data_folder)

        # Load cached data to report stats
        from core.pdf_training_extractor import load_cached_data
        cached = load_cached_data()

        return jsonify({
            "status": "success",
            "message": "Model trained from PDF data",
            "pdfs_processed": len(cached[cached["source_file"] != "augmented_synthetic"]) if "source_file" in cached.columns else len(cached),
            "total_training_samples": len(cached),
        })
    except Exception as e:
        logger.error(f"PDF training error: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/add-training-pdf", methods=["POST"])
def add_training_pdf():
    """Upload a single PDF, extract features, append to training data, and retrain."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Send a PDF as 'file' in multipart form data."}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    try:
        # Save to Data folder
        data_folder = os.path.join(os.path.dirname(__file__), "Data")
        os.makedirs(data_folder, exist_ok=True)
        filepath = os.path.join(data_folder, file.filename)
        file.save(filepath)

        # Extract features and append to training cache
        from core.pdf_training_extractor import extract_and_append
        updated_df = extract_and_append(filepath)

        # Retrain model with updated data
        retrain = (request.form.get("retrain", "true")).lower() == "true"
        if retrain:
            from models.credit_risk_model import CreditRiskModel
            model = CreditRiskModel()
            model.train_from_pdfs()

        return jsonify({
            "status": "success",
            "message": f"PDF '{file.filename}' processed and added to training data",
            "file_saved": filepath,
            "total_training_samples": len(updated_df),
            "model_retrained": retrain,
        })
    except Exception as e:
        logger.error(f"Add training PDF error: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


# ═══════════════════════════════════════════════════════════════════
#  API - STATUS & CONFIG
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/status")
def get_status():
    """Get pipeline status."""
    return jsonify(pipeline_state)


@app.route("/api/databricks-status")
def databricks_status():
    """Check Databricks connection status."""
    try:
        from core.databricks_connector import DatabricksConnector
        db = DatabricksConnector()
        status = db.get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n")
    print("  ====================================================")
    print("  |                                                    |")
    print("  |    I N T E L L I - C R E D I T                    |")
    print("  |    AI-Powered Credit Decisioning Engine            |")
    print("  |                                                    |")
    print("  |    Developed by Team SPB                           |")
    print("  |                                                    |")
    print("  |    http://localhost:5000                            |")
    print("  |                                                    |")
    print("  ====================================================")
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG, use_reloader=False)
