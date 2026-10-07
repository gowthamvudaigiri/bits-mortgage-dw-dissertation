"""
Applies rbac_and_governance.sql programmatically — lets an agent (or you)
run the role/grant/masking-policy setup without manually pasting into
Snowsight. Reads the same environment variables as load_to_snowflake.py,
plus two more for the placeholders in the SQL file.

Required env vars:
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD   (connection)
    SNOWFLAKE_ADMIN_USERNAME                                (who gets MTG_DW_ADMIN — usually same as SNOWFLAKE_USER)
    DEMO_ANALYST_PASSWORD                                   (temp password for the new MRCOOPER_DEMO_ANALYST user)
"""

import os
import re
import snowflake.connector
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SF_ACCOUNT  = os.environ.get("SNOWFLAKE_ACCOUNT", "")
SF_USER     = os.environ.get("SNOWFLAKE_USER", "")
SF_PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD", "")
ADMIN_USERNAME       = os.environ.get("SNOWFLAKE_ADMIN_USERNAME", SF_USER)
DEMO_ANALYST_PASSWORD = os.environ.get("DEMO_ANALYST_PASSWORD", "")

SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rbac_and_governance.sql")


def load_statements(path, replacements):
    with open(path) as f:
        raw = f.read()
    for old, new in replacements.items():
        raw = raw.replace(old, new)
    # Strip full-line comments, then split on ';'
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
    cleaned = "\n".join(lines)
    statements = [s.strip() for s in cleaned.split(";")]
    return [s for s in statements if s]


def main():
    missing = [n for n, v in [("SNOWFLAKE_ACCOUNT", SF_ACCOUNT), ("SNOWFLAKE_USER", SF_USER),
                               ("SNOWFLAKE_PASSWORD", SF_PASSWORD),
                               ("DEMO_ANALYST_PASSWORD", DEMO_ANALYST_PASSWORD)] if not v]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    statements = load_statements(SQL_FILE, {
        "<your_username>": ADMIN_USERNAME,
        "<set_a_temporary_password>": DEMO_ANALYST_PASSWORD,
    })

    print(f"Connecting to Snowflake as {SF_USER}...")
    con = snowflake.connector.connect(account=SF_ACCOUNT, user=SF_USER, password=SF_PASSWORD)
    cur = con.cursor()

    print(f"Applying {len(statements)} statements from rbac_and_governance.sql...\n")
    for i, stmt in enumerate(statements, 1):
        first_line = stmt.splitlines()[0][:80]
        print(f"[{i}/{len(statements)}] {first_line}")
        try:
            cur.execute(stmt)
        except Exception as e:
            print(f"   WARNING: statement failed — {e}")
            print(f"   Statement was: {stmt[:200]}")

    print("\n--- Verification: Admin view of DIM_BORROWER (should show real synthetic IDs) ---")
    cur.execute("USE ROLE MTG_DW_ADMIN")
    rows = cur.execute("SELECT synthetic_borrower_id FROM DIM_BORROWER LIMIT 5").fetchall()
    for r in rows:
        print("  ", r[0])

    cur.close()
    con.close()
    print("\nDone. Roles, views, and masking policy applied.")
    print(f"Second login created: MRCOOPER_DEMO_ANALYST (role MTG_DATA_ANALYST).")
    print("To verify masking: log in as that user (or `USE ROLE MTG_DATA_ANALYST;` in a new "
          "session) and run `SELECT * FROM VW_DELINQUENCY_TREND LIMIT 5;` — base-table access "
          "will be denied, and the view works with no borrower identifier exposed.")


if __name__ == "__main__":
    main()
