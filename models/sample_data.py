"""
Sample Data Generator
======================
Generate realistic synthetic Indian corporate credit data for demo and ML training.
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def generate_company_profile(company_type: str = "healthy") -> dict:
    """Generate a realistic Indian company financial profile."""
    profiles = {
        "healthy": {
            "company_name": "Aravind Industries Pvt Ltd",
            "cin": "U29100MH2010PTC123456",
            "industry": "Manufacturing - Auto Components",
            "incorporation_date": "2010-04-15",
            "registered_office": "Mumbai, Maharashtra",
            "promoter_name": "Rajesh K. Sharma",
            "promoter_holding_pct": 72.5,
            "years_in_business": 16,
            "employee_count": 850,
            "revenue": {"value": 485, "unit": "Cr", "growth_pct": 12.5},
            "ebitda": {"value": 72.75, "unit": "Cr", "margin_pct": 15.0},
            "pat": {"value": 38.8, "unit": "Cr", "margin_pct": 8.0},
            "total_debt": {"value": 120, "unit": "Cr"},
            "net_worth": {"value": 210, "unit": "Cr"},
            "total_assets": {"value": 380, "unit": "Cr"},
            "tangible_net_worth": {"value": 195, "unit": "Cr"},
            "working_capital": {"value": 45, "unit": "Cr"},
            "debt_equity_ratio": 0.57,
            "current_ratio": 1.65,
            "interest_coverage_ratio": 4.2,
            "dscr": 2.1,
            "cash_flow_from_operations": {"value": 55, "unit": "Cr"},
            "debtors_days": 65,
            "creditors_days": 45,
            "inventory_days": 30,
            "credit_rating": "CRISIL A- (Stable)",
            "key_strengths": [
                "Strong promoter with 15+ years industry experience",
                "Diversified customer base - top 3 auto OEMs",
                "Consistent revenue growth above 10% CAGR",
                "Healthy DSCR and interest coverage",
            ],
            "key_risks": [
                "Concentration in auto sector (cyclical)",
                "Working capital intensive business",
            ],
            "red_flags": [],
        },
        "risky": {
            "company_name": "Global Impex Trading Co.",
            "cin": "U51909DL2015PTC278901",
            "industry": "Trading - Metals & Minerals",
            "incorporation_date": "2015-08-20",
            "registered_office": "New Delhi",
            "promoter_name": "Vikram Agarwal",
            "promoter_holding_pct": 95.0,
            "years_in_business": 11,
            "employee_count": 45,
            "revenue": {"value": 320, "unit": "Cr", "growth_pct": -8.5},
            "ebitda": {"value": 9.6, "unit": "Cr", "margin_pct": 3.0},
            "pat": {"value": -5.2, "unit": "Cr", "margin_pct": -1.6},
            "total_debt": {"value": 180, "unit": "Cr"},
            "net_worth": {"value": 35, "unit": "Cr"},
            "total_assets": {"value": 240, "unit": "Cr"},
            "tangible_net_worth": {"value": 20, "unit": "Cr"},
            "working_capital": {"value": -12, "unit": "Cr"},
            "debt_equity_ratio": 5.14,
            "current_ratio": 0.82,
            "interest_coverage_ratio": 0.8,
            "dscr": 0.65,
            "cash_flow_from_operations": {"value": -15, "unit": "Cr"},
            "debtors_days": 145,
            "creditors_days": 30,
            "inventory_days": 5,
            "credit_rating": "ICRA BB- (Negative)",
            "key_strengths": [
                "Long-standing relationships with overseas suppliers",
            ],
            "key_risks": [
                "Very high leverage - D/E ratio of 5.14x",
                "Negative working capital and operating cash flow",
                "Loss-making - PAT negative for 2 consecutive years",
                "Single promoter - high key-man risk",
                "Trading business - low margin, high risk",
            ],
            "red_flags": [
                "Promoter has 3 active court cases",
                "Qualified audit opinion for FY24",
                "Suspicious related-party transactions worth ₹85 Cr",
                "High debtor days (145) - potential circular trading",
            ],
        },
        "growth": {
            "company_name": "Nexus Tech Solutions Pvt Ltd",
            "cin": "U72200KA2018PTC987654",
            "industry": "IT Services & Software",
            "incorporation_date": "2018-02-10",
            "registered_office": "Bengaluru, Karnataka",
            "promoter_name": "Aditya Menon",
            "promoter_holding_pct": 55.0,
            "years_in_business": 8,
            "employee_count": 320,
            "revenue": {"value": 150, "unit": "Cr", "growth_pct": 45.0},
            "ebitda": {"value": 15, "unit": "Cr", "margin_pct": 10.0},
            "pat": {"value": -8, "unit": "Cr", "margin_pct": -5.3},
            "total_debt": {"value": 25, "unit": "Cr"},
            "net_worth": {"value": 180, "unit": "Cr"},
            "total_assets": {"value": 220, "unit": "Cr"},
            "tangible_net_worth": {"value": 160, "unit": "Cr"},
            "working_capital": {"value": 85, "unit": "Cr"},
            "debt_equity_ratio": 0.14,
            "current_ratio": 2.8,
            "interest_coverage_ratio": 3.5,
            "dscr": 1.5,
            "cash_flow_from_operations": {"value": 5, "unit": "Cr"},
            "debtors_days": 90,
            "creditors_days": 30,
            "inventory_days": 0,
            "credit_rating": "CRISIL BBB+ (Positive)",
            "key_strengths": [
                "Exceptional revenue growth at 45% YoY",
                "Strong liquidity and recent equity fundraise of ₹100 Cr",
                "Asset-light tech business model",
            ],
            "key_risks": [
                "Currently loss-making at PAT level (cash burn)",
                "High debtor days indicating delayed collections from clients",
            ],
            "red_flags": [],
        },
        "stable": {
            "company_name": "Heritage Retail Marts Ltd",
            "cin": "L51909TN2005PLC345678",
            "industry": "Retail & FMCG",
            "incorporation_date": "2005-09-12",
            "registered_office": "Chennai, Tamil Nadu",
            "promoter_name": "Srinivasan Iyer",
            "promoter_holding_pct": 62.5,
            "years_in_business": 21,
            "employee_count": 1250,
            "revenue": {"value": 1250, "unit": "Cr", "growth_pct": 8.5},
            "ebitda": {"value": 105, "unit": "Cr", "margin_pct": 8.4},
            "pat": {"value": 55, "unit": "Cr", "margin_pct": 4.4},
            "total_debt": {"value": 85, "unit": "Cr"},
            "net_worth": {"value": 340, "unit": "Cr"},
            "total_assets": {"value": 520, "unit": "Cr"},
            "tangible_net_worth": {"value": 320, "unit": "Cr"},
            "working_capital": {"value": 65, "unit": "Cr"},
            "debt_equity_ratio": 0.25,
            "current_ratio": 1.4,
            "interest_coverage_ratio": 6.8,
            "dscr": 3.2,
            "cash_flow_from_operations": {"value": 82, "unit": "Cr"},
            "debtors_days": 15,
            "creditors_days": 55,
            "inventory_days": 45,
            "credit_rating": "ICRA AA- (Stable)",
            "key_strengths": [
                "Established market position with 20+ years track record",
                "Very strong cash flows and coverage metrics",
                "Low leverage with D/E at 0.25x",
            ],
            "key_risks": [
                "Moderate margin business typical to retail",
                "High competition in organized retail space",
            ],
            "red_flags": [],
        }
    }

    return profiles.get(company_type, profiles["healthy"])


def generate_gst_data(company_type: str = "healthy") -> pd.DataFrame:
    """Generate GST filing data (GSTR-1 returns)."""
    months = pd.date_range(start="2025-04-01", periods=12, freq="MS")
    data = []

    if company_type == "healthy":
        base_revenue = 3500  # ~ ₹3500L/month for ₹420Cr annual
        growth_rate = 0.01
        volatility = 0.08
    elif company_type == "growth":
        base_revenue = 800
        growth_rate = 0.04
        volatility = 0.15
    elif company_type == "stable":
        base_revenue = 9500
        growth_rate = 0.005
        volatility = 0.05
    else:
        base_revenue = 2500
        growth_rate = -0.015
        volatility = 0.25

    for i, month in enumerate(months):
        monthly_rev = base_revenue * (1 + growth_rate * i) * (1 + random.gauss(0, volatility))
        monthly_rev = max(monthly_rev, 100)

        igst = monthly_rev * 0.18 * 0.4
        cgst = monthly_rev * 0.09 * 0.6
        sgst = cgst

        data.append({
            "Month": month.strftime("%b-%Y"),
            "GSTIN": "27AABCF1234M1Z5" if company_type in ["healthy", "stable"] else "07AABCF5678N1Z2",
            "Taxable_Value_Lakhs": round(monthly_rev, 2),
            "IGST": round(igst, 2),
            "CGST": round(cgst, 2),
            "SGST": round(sgst, 2),
            "Total_Tax": round(igst + cgst + sgst, 2),
            "Invoice_Count": random.randint(80, 250) if company_type == "healthy" else (random.randint(15, 60) if company_type == "growth" else (random.randint(1000, 3000) if company_type == "stable" else random.randint(10, 40))),
            "Filing_Status": "Filed" if random.random() > 0.05 else "Late Filed",
        })

    return pd.DataFrame(data)


def generate_bank_statement(company_type: str = "healthy") -> pd.DataFrame:
    """Generate bank statement data."""
    dates = pd.date_range(start="2025-04-01", periods=90, freq="B")  # business days
    data = []

    balance = 5000000 if company_type in ["healthy", "stable", "growth"] else 800000

    for date in dates:
        # Multiple transactions per day
        num_txns = random.randint(1, 5) if company_type == "healthy" else (random.randint(3, 8) if company_type == "stable" else (random.randint(1, 3) if company_type == "growth" else random.randint(0, 3)))

        for _ in range(num_txns):
            is_credit = random.random() > 0.45

            if company_type in ["healthy", "stable", "growth"]:
                if is_credit:
                    amount = random.choice([
                        round(random.uniform(100000, 2500000), 2),  # Customer payments
                        round(random.uniform(50000, 500000), 2),    # Small receipts
                    ])
                    narration = random.choice([
                        "NEFT-Customer Payment-INV",
                        "RTGS-Trade Receivable",
                        "IMPS-Advance Received",
                        "Cheque Deposit",
                    ])
                else:
                    amount = random.choice([
                        round(random.uniform(50000, 1500000), 2),
                        round(random.uniform(20000, 300000), 2),
                    ])
                    narration = random.choice([
                        "NEFT-Vendor Payment",
                        "RTGS-Raw Material Purchase",
                        "Salary Payment",
                        "EMI-Term Loan",
                        "Electricity/Utility Bill",
                        "GST Payment",
                    ])
            else:
                if is_credit:
                    amount = round(random.uniform(500000, 5000000), 2)
                    narration = random.choice([
                        "RTGS-Import Payment Received",
                        "NEFT-Trading Receipt",
                        "NEFT-Related Party Transfer",
                    ])
                else:
                    amount = round(random.uniform(500000, 5000000), 2)
                    narration = random.choice([
                        "RTGS-Outward Remittance",
                        "NEFT-Payment to Associate",
                        "NEFT-Related Party Payment",
                        "Cash Withdrawal",
                    ])

            credit = amount if is_credit else 0
            debit = amount if not is_credit else 0
            balance += credit - debit

            data.append({
                "Date": date.strftime("%d-%m-%Y"),
                "Narration": narration + f"-{random.randint(1000, 9999)}",
                "Reference_No": f"TXN{random.randint(100000, 999999)}",
                "Credit": credit,
                "Debit": debit,
                "Balance": round(balance, 2),
            })

    return pd.DataFrame(data)


def generate_training_data(n_samples: int = 1000) -> pd.DataFrame:
    """Generate synthetic training data for the ML credit risk model."""
    np.random.seed(42)

    data = {
        "revenue_growth": np.random.normal(8, 15, n_samples),
        "ebitda_margin": np.random.normal(12, 8, n_samples),
        "pat_margin": np.random.normal(5, 7, n_samples),
        "debt_equity_ratio": np.abs(np.random.exponential(1.2, n_samples)),
        "current_ratio": np.abs(np.random.normal(1.5, 0.5, n_samples)),
        "dscr": np.abs(np.random.normal(1.8, 0.7, n_samples)),
        "interest_coverage": np.abs(np.random.normal(3.0, 1.5, n_samples)),
        "promoter_holding": np.random.uniform(20, 100, n_samples),
        "years_in_business": np.random.randint(1, 40, n_samples),
        "debtors_days": np.random.randint(15, 200, n_samples),
        "sentiment_score": np.random.uniform(-1, 1, n_samples),
        "litigation_count": np.random.poisson(1.5, n_samples),
        "cross_verification_score": np.random.uniform(40, 100, n_samples),
        "industry_risk_score": np.random.uniform(1, 10, n_samples),
    }

    df = pd.DataFrame(data)

    # Generate target based on features (realistic logic)
    risk_score = (
        -0.3 * df["revenue_growth"] / 100
        + 0.5 * df["debt_equity_ratio"]
        - 0.2 * df["current_ratio"]
        - 0.3 * df["dscr"]
        - 0.2 * df["interest_coverage"] / 10
        - 0.1 * df["ebitda_margin"] / 100
        + 0.15 * df["debtors_days"] / 100
        - 0.2 * df["sentiment_score"]
        + 0.25 * df["litigation_count"]
        - 0.15 * df["cross_verification_score"] / 100
        + 0.1 * df["industry_risk_score"] / 10
        + np.random.normal(0, 0.3, n_samples)
    )

    # Binary: 1 = high risk (default/stress), 0 = low risk
    df["target"] = (risk_score > np.percentile(risk_score, 70)).astype(int)

    return df


def generate_augmented_training_data(real_df: pd.DataFrame, n_augmented: int = 500) -> pd.DataFrame:
    """
    Generate synthetic training data whose distributions are centered around
    the real PDF-extracted data. This produces more realistic augmented samples
    than the purely random generation in generate_training_data().

    Args:
        real_df: DataFrame with real features extracted from PDFs
                 (must include the 14 feature columns and 'target')
        n_augmented: Number of synthetic samples to generate

    Returns:
        Combined DataFrame of real + augmented data
    """
    feature_cols = [
        "revenue_growth", "ebitda_margin", "pat_margin",
        "debt_equity_ratio", "current_ratio", "dscr",
        "interest_coverage", "promoter_holding", "years_in_business",
        "debtors_days", "sentiment_score", "litigation_count",
        "cross_verification_score", "industry_risk_score",
    ]

    np.random.seed(42)

    if len(real_df) == 0:
        # Fall back to default generation if no real data
        return generate_training_data(n_augmented)

    # Compute statistics from real data
    stats = {}
    for col in feature_cols:
        if col in real_df.columns:
            vals = real_df[col].dropna().astype(float)
            if len(vals) > 0:
                stats[col] = {"mean": vals.mean(), "std": max(vals.std(), 0.1)}
            else:
                stats[col] = {"mean": 0, "std": 1}
        else:
            stats[col] = {"mean": 0, "std": 1}

    # Generate augmented samples centered around real distributions
    # Add controlled noise (wider std) to increase diversity
    augmented = {}
    for col in feature_cols:
        mean = stats[col]["mean"]
        std = stats[col]["std"] * 2.0  # Widen distribution for diversity

        if col in ("litigation_count",):
            augmented[col] = np.abs(np.random.poisson(max(mean, 0.5), n_augmented)).astype(float)
        elif col in ("years_in_business",):
            augmented[col] = np.clip(np.random.normal(mean, std, n_augmented), 1, 50).astype(float)
        elif col in ("debt_equity_ratio", "current_ratio", "dscr", "interest_coverage"):
            augmented[col] = np.abs(np.random.normal(mean, std, n_augmented))
        elif col in ("promoter_holding",):
            augmented[col] = np.clip(np.random.normal(mean, std, n_augmented), 0, 100)
        elif col in ("debtors_days",):
            augmented[col] = np.clip(np.random.normal(mean, std, n_augmented), 5, 300)
        elif col in ("sentiment_score",):
            augmented[col] = np.clip(np.random.normal(mean, std, n_augmented), -1, 1)
        elif col in ("cross_verification_score",):
            augmented[col] = np.clip(np.random.normal(mean, std, n_augmented), 0, 100)
        elif col in ("industry_risk_score",):
            augmented[col] = np.clip(np.random.normal(mean, std, n_augmented), 1, 10)
        else:
            augmented[col] = np.random.normal(mean, std, n_augmented)

    aug_df = pd.DataFrame(augmented)

    # Generate target using the same heuristic logic as pdf_training_extractor
    risk_score = (
        -0.3 * aug_df["revenue_growth"] / 100
        + 0.5 * aug_df["debt_equity_ratio"]
        - 0.2 * aug_df["current_ratio"]
        - 0.3 * aug_df["dscr"]
        - 0.2 * aug_df["interest_coverage"] / 10
        - 0.1 * aug_df["ebitda_margin"] / 100
        + 0.15 * aug_df["debtors_days"] / 100
        - 0.2 * aug_df["sentiment_score"]
        + 0.25 * aug_df["litigation_count"]
        - 0.15 * aug_df["cross_verification_score"] / 100
        + 0.1 * aug_df["industry_risk_score"] / 10
        + np.random.normal(0, 0.3, n_augmented)
    )
    aug_df["target"] = (risk_score > np.percentile(risk_score, 70)).astype(int)

    # Mark source for traceability
    aug_df["source_file"] = "augmented_synthetic"

    # Combine real + augmented
    combined = pd.concat([real_df, aug_df], ignore_index=True)
    return combined
