"""
Databricks Connector
=====================
Integration with Databricks for multi-source data ingestion
and high-latency pipeline management.
"""

import os
import json
import logging
from typing import Optional

import pandas as pd

from config import Config

logger = logging.getLogger(__name__)


class DatabricksConnector:
    """Connect to Databricks for data pipeline operations."""

    def __init__(self):
        self.host = Config.DATABRICKS_HOST
        self.token = Config.DATABRICKS_TOKEN
        self.warehouse_id = Config.DATABRICKS_SQL_WAREHOUSE_ID
        self.catalog = Config.DATABRICKS_CATALOG
        self.schema = Config.DATABRICKS_SCHEMA
        self._connection = None
        self._workspace_client = None
        self.is_connected = False

    def connect(self) -> bool:
        """Establish connection to Databricks."""
        if not self.host or not self.token:
            logger.warning("Databricks credentials not configured. Running in local mode.")
            return False

        try:
            from databricks import sql as databricks_sql
            self._connection = databricks_sql.connect(
                server_hostname=self.host.replace("https://", ""),
                http_path=f"/sql/1.0/warehouses/{self.warehouse_id}",
                access_token=self.token,
            )
            self.is_connected = True
            logger.info("Connected to Databricks SQL Warehouse")
            return True
        except Exception as e:
            logger.error(f"Databricks connection failed: {e}")
            return False

    def connect_workspace(self) -> bool:
        """Connect to Databricks workspace for file/job operations."""
        if not self.host or not self.token:
            return False
        try:
            from databricks.sdk import WorkspaceClient
            self._workspace_client = WorkspaceClient(
                host=self.host,
                token=self.token,
            )
            logger.info("Connected to Databricks Workspace")
            return True
        except Exception as e:
            logger.error(f"Databricks workspace connection failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    #  DATA OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Databricks")

        try:
            cursor = self._connection.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            cursor.close()
            return pd.DataFrame(data, columns=columns)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def upload_data(self, df: pd.DataFrame, table_name: str,
                    mode: str = "overwrite") -> bool:
        """Upload DataFrame to Databricks table."""
        if not self.is_connected:
            logger.warning("Not connected to Databricks, saving locally instead")
            return self._save_local(df, table_name)

        try:
            full_table = f"{self.catalog}.{self.schema}.{table_name}"
            # Create table with data
            cursor = self._connection.cursor()

            # Create table schema
            col_defs = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                if "int" in dtype:
                    sql_type = "INT"
                elif "float" in dtype:
                    sql_type = "DOUBLE"
                else:
                    sql_type = "STRING"
                col_defs.append(f"`{col}` {sql_type}")

            if mode == "overwrite":
                cursor.execute(f"DROP TABLE IF EXISTS {full_table}")

            create_sql = f"CREATE TABLE IF NOT EXISTS {full_table} ({', '.join(col_defs)})"
            cursor.execute(create_sql)

            # Insert data in batches
            batch_size = 100
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i + batch_size]
                values_list = []
                for _, row in batch.iterrows():
                    vals = []
                    for v in row.values:
                        if pd.isna(v):
                            vals.append("NULL")
                        elif isinstance(v, str):
                            vals.append(f"'{v.replace(chr(39), chr(39)+chr(39))}'")
                        else:
                            vals.append(str(v))
                    values_list.append(f"({', '.join(vals)})")

                insert_sql = f"INSERT INTO {full_table} VALUES {', '.join(values_list)}"
                cursor.execute(insert_sql)

            cursor.close()
            logger.info(f"Uploaded {len(df)} rows to {full_table}")
            return True
        except Exception as e:
            logger.error(f"Data upload failed: {e}")
            return self._save_local(df, table_name)

    def fetch_company_data(self, company_name: str) -> dict:
        """Fetch all available data for a company from Databricks."""
        if not self.is_connected:
            return {"error": "Not connected to Databricks", "local_mode": True}

        result = {}
        tables = [
            "financial_statements",
            "gst_filings",
            "bank_statements",
            "credit_ratings",
            "litigation_records",
        ]

        for table in tables:
            try:
                full_table = f"{self.catalog}.{self.schema}.{table}"
                query = f"SELECT * FROM {full_table} WHERE company_name LIKE '%{company_name}%' LIMIT 1000"
                df = self.execute_query(query)
                result[table] = {
                    "data": df.to_dict(orient="records"),
                    "row_count": len(df),
                }
            except Exception as e:
                result[table] = {"error": str(e), "data": []}

        return result

    def setup_schema(self) -> bool:
        """Create the Databricks schema and tables if they don't exist."""
        if not self.is_connected:
            return False

        try:
            cursor = self._connection.cursor()

            cursor.execute(f"CREATE CATALOG IF NOT EXISTS {self.catalog}")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{self.schema}")

            tables_sql = {
                "financial_statements": """
                    CREATE TABLE IF NOT EXISTS {catalog}.{schema}.financial_statements (
                        company_name STRING,
                        financial_year STRING,
                        revenue DOUBLE,
                        ebitda DOUBLE,
                        pat DOUBLE,
                        total_debt DOUBLE,
                        net_worth DOUBLE,
                        debt_equity_ratio DOUBLE,
                        current_ratio DOUBLE,
                        dscr DOUBLE,
                        interest_coverage DOUBLE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "gst_filings": """
                    CREATE TABLE IF NOT EXISTS {catalog}.{schema}.gst_filings (
                        company_name STRING,
                        gstin STRING,
                        month STRING,
                        taxable_value DOUBLE,
                        igst DOUBLE,
                        cgst DOUBLE,
                        sgst DOUBLE,
                        filing_status STRING,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "analysis_results": """
                    CREATE TABLE IF NOT EXISTS {catalog}.{schema}.analysis_results (
                        company_name STRING,
                        analysis_date STRING,
                        overall_score DOUBLE,
                        risk_grade STRING,
                        recommendation STRING,
                        five_cs_json STRING,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
            }

            for table_name, sql in tables_sql.items():
                cursor.execute(sql.format(catalog=self.catalog, schema=self.schema))

            cursor.close()
            logger.info("Databricks schema setup complete")
            return True
        except Exception as e:
            logger.error(f"Schema setup failed: {e}")
            return False

    def save_analysis_results(self, company_name: str, results: dict) -> bool:
        """Save analysis results to Databricks for tracking."""
        if not self.is_connected:
            return False

        try:
            scoring = results.get("scoring", {})
            df = pd.DataFrame([{
                "company_name": company_name,
                "analysis_date": pd.Timestamp.now().isoformat(),
                "overall_score": scoring.get("overall_score", 0),
                "risk_grade": scoring.get("risk_grade", ""),
                "recommendation": scoring.get("recommendation", {}).get("decision", ""),
                "five_cs_json": json.dumps(scoring.get("scores", {})),
            }])
            return self.upload_data(df, "analysis_results", mode="append")
        except Exception as e:
            logger.error(f"Failed to save results to Databricks: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    #  LOCAL FALLBACK
    # ═══════════════════════════════════════════════════════════════

    def _save_local(self, df: pd.DataFrame, table_name: str) -> bool:
        """Save data locally as CSV when Databricks is unavailable."""
        try:
            local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(local_dir, exist_ok=True)
            filepath = os.path.join(local_dir, f"{table_name}.csv")
            df.to_csv(filepath, index=False)
            logger.info(f"Saved locally: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Local save failed: {e}")
            return False

    def get_status(self) -> dict:
        """Get current Databricks connection and configuration status."""
        return {
            "connected": self.is_connected,
            "host": self.host[:30] + "..." if self.host else "Not configured",
            "catalog": self.catalog,
            "schema": self.schema,
            "warehouse_configured": bool(self.warehouse_id),
        }

    def close(self):
        """Close all connections."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
        self.is_connected = False
