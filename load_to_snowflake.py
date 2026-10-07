"""
Loads the synthetic mortgage-servicing dataset into a real Snowflake trial account.

Prerequisites:
    pip install snowflake-connector-python pandas

Before running:
    1. Set the connection variables below (account, user, password).
    2. Make sure the CSV files from synthetic_mortgage_data.zip are unzipped
       into the SAME folder as this script (or update DATA_DIR below).

What this script does, in order:
    1. Creates the warehouse, database, and schema (idempotent — safe to re-run).
    2. Creates the 7 tables (6 dimensions + 1 fact).
    3. Loads each CSV via Snowflake's PUT + COPY INTO (internal stage) —
       this works for files of any size, including the 141 MB fact file,
       unlike the Snowsight drag-and-drop UI which has a practical limit
       of roughly 50 MB per file.
    4. Prints row counts so you can confirm the load matches Section 6.3
       of the Mid-Semester Report (1,569,088 fact rows total).
"""

import snowflake.connector
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ---------------- CONNECTION CONFIG ----------------
# Reads from environment variables first (preferred — no secrets in this file).
# Falls back to the placeholder strings only if the env var isn't set.
SF_ACCOUNT  = os.environ.get("SNOWFLAKE_ACCOUNT",  "<your_account_identifier>")
SF_USER     = os.environ.get("SNOWFLAKE_USER",     "<your_username>")
SF_PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD", "<your_password>")
DATA_DIR    = os.path.dirname(os.path.abspath(__file__))   # folder containing the CSVs
# -----------------------------------------------------

def _check_config():
    missing = [n for n, v in [("SNOWFLAKE_ACCOUNT", SF_ACCOUNT), ("SNOWFLAKE_USER", SF_USER),
                               ("SNOWFLAKE_PASSWORD", SF_PASSWORD)] if v.startswith("<")]
    if missing:
        raise SystemExit(
            f"Missing Snowflake credentials: {', '.join(missing)}.\n"
            f"Set them as environment variables, e.g.:\n"
            f"  export SNOWFLAKE_ACCOUNT=ab12345.us-east-1\n"
            f"  export SNOWFLAKE_USER=your_username\n"
            f"  export SNOWFLAKE_PASSWORD=your_password\n"
        )

WAREHOUSE = "MTG_ANALYTICS_WH"
DATABASE  = "MTG_SERVICING_DW"
SCHEMA    = "CORE"

DDL_STATEMENTS = [
    f"""CREATE WAREHOUSE IF NOT EXISTS {WAREHOUSE}
          WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE""",
    f"CREATE DATABASE IF NOT EXISTS {DATABASE}",
    f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}",
    f"USE WAREHOUSE {WAREHOUSE}",
    f"USE SCHEMA {DATABASE}.{SCHEMA}",

    """CREATE OR REPLACE TABLE DIM_LOAN (
        loan_sk BIGINT PRIMARY KEY, synthetic_loan_id VARCHAR(10), origination_date DATE,
        loan_type VARCHAR(30), product_type VARCHAR(30), original_upb NUMERIC(12,2),
        interest_rate NUMERIC(5,3), term_months INT)""",

    """CREATE OR REPLACE TABLE DIM_BORROWER (
        borrower_sk BIGINT PRIMARY KEY, synthetic_borrower_id VARCHAR(12), state VARCHAR(2),
        credit_band VARCHAR(20), income_band VARCHAR(20))""",

    """CREATE OR REPLACE TABLE DIM_DATE (
        date_sk INT PRIMARY KEY, calendar_date DATE, month INT, quarter INT, year INT)""",

    """CREATE OR REPLACE TABLE DIM_INVESTOR (
        investor_sk INT PRIMARY KEY, investor_name VARCHAR(60), investor_type VARCHAR(30))""",

    """CREATE OR REPLACE TABLE DIM_SERVICER (
        servicer_sk INT PRIMARY KEY, servicing_branch VARCHAR(60), region VARCHAR(30))""",

    """CREATE OR REPLACE TABLE DIM_DELINQUENCY_BUCKET (
        bucket_sk INT PRIMARY KEY, dpd_range VARCHAR(20), bucket_label VARCHAR(30))""",

    """CREATE OR REPLACE TABLE FACT_LOAN_SERVICING_EVENT (
        event_sk BIGINT PRIMARY KEY, loan_sk BIGINT REFERENCES DIM_LOAN(loan_sk),
        date_sk INT REFERENCES DIM_DATE(date_sk), borrower_sk BIGINT REFERENCES DIM_BORROWER(borrower_sk),
        investor_sk INT REFERENCES DIM_INVESTOR(investor_sk), servicer_sk INT REFERENCES DIM_SERVICER(servicer_sk),
        bucket_sk INT REFERENCES DIM_DELINQUENCY_BUCKET(bucket_sk), event_type VARCHAR(30),
        scheduled_amount NUMERIC(12,2), actual_amount NUMERIC(12,2), principal_amt NUMERIC(12,2),
        interest_amt NUMERIC(12,2), escrow_amt NUMERIC(12,2), late_fee_amt NUMERIC(12,2),
        days_past_due INT, unpaid_principal_bal NUMERIC(12,2),
        scheduled_remit_date DATE, actual_remit_date DATE)""",
]

# (table_name, csv_filename, column_order_matching_csv_header)
LOAD_TARGETS = [
    ("DIM_DATE", "dim_date.csv"),
    ("DIM_INVESTOR", "dim_investor.csv"),
    ("DIM_SERVICER", "dim_servicer.csv"),
    ("DIM_DELINQUENCY_BUCKET", "dim_delinquency_bucket.csv"),
    ("DIM_LOAN", "dim_loan.csv"),
    ("DIM_BORROWER", "dim_borrower.csv"),
    ("FACT_LOAN_SERVICING_EVENT", "fact_loan_servicing_event.csv"),  # largest, loads last
]

def main():
    _check_config()
    print("Connecting to Snowflake...")
    con = snowflake.connector.connect(
        account=SF_ACCOUNT, user=SF_USER, password=SF_PASSWORD,
    )
    cur = con.cursor()

    print("\n--- Creating warehouse / database / schema / tables ---")
    for stmt in DDL_STATEMENTS:
        cur.execute(stmt)
    print("Objects created.")

    cur.execute(f"CREATE OR REPLACE STAGE {DATABASE}.{SCHEMA}.LOAD_STAGE "
                f"FILE_FORMAT = (TYPE=CSV SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='\"' "
                f"NULL_IF=('','NaT','nan') EMPTY_FIELD_AS_NULL=TRUE)")

    for table, filename in LOAD_TARGETS:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            print(f"  SKIP {table}: {filename} not found in {DATA_DIR}")
            continue
        print(f"\n--- Loading {table} from {filename} ---")
        cur.execute(f"PUT file://{path} @{DATABASE}.{SCHEMA}.LOAD_STAGE OVERWRITE=TRUE AUTO_COMPRESS=TRUE")
        result = cur.execute(
            f"COPY INTO {DATABASE}.{SCHEMA}.{table} "
            f"FROM @{DATABASE}.{SCHEMA}.LOAD_STAGE/{filename}.gz "
            f"FILE_FORMAT=(TYPE=CSV SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='\"' "
            f"NULL_IF=('','NaT','nan') EMPTY_FIELD_AS_NULL=TRUE) "
            f"ON_ERROR=ABORT_STATEMENT"
        ).fetchall()
        print(f"  COPY result: {result}")

    print("\n--- Row counts ---")
    for table, _ in LOAD_TARGETS:
        count = cur.execute(f"SELECT COUNT(*) FROM {DATABASE}.{SCHEMA}.{table}").fetchone()[0]
        print(f"  {table}: {count:,}")

    cur.close()
    con.close()
    print("\nDone. Expected FACT_LOAN_SERVICING_EVENT count: 1,569,088.")

if __name__ == "__main__":
    main()
