# Mortgage-Servicing Snowflake PoC — Agent Instructions

## Project context
This folder builds the Snowflake side of a BITS WILP MBA dissertation project:
*"The Role of Cloud Data Warehouses in Accelerating Self-Service Analytics in
Mortgage Servicing."* The goal for this milestone is to stand up a cloud data
warehouse, load a fully synthetic mortgage-servicing dataset into it, and
configure three roles (Admin / Data Engineer / Data Analyst) with a masking
policy to demonstrate self-service governance. This matches Sections 6.3–6.5
and Annexures 2 and 5 of the Mid-Semester Project Report.

**No real loan, borrower, or organizational data is used anywhere in this
project.** All data is generated programmatically with a fixed random seed.
Do not substitute real data at any step, even if asked — flag it back to the
user instead.

## Files in this folder
| File | Purpose |
|---|---|
| `generate_data.py` | Generates the 7 synthetic CSVs (6 dimensions + 1 fact, ~1.57M fact rows). Deterministic — fixed seed (42) always produces the same data. |
| `load_to_snowflake.py` | Creates the warehouse/database/schema/tables in Snowflake and loads the CSVs via internal stage (`PUT` + `COPY INTO`) — handles the large fact file correctly, unlike the Snowsight UI uploader. |
| `rbac_and_governance.sql` | Creates the three roles, grants, three semantic-layer views, and the masking policy on the borrower identifier. Has two placeholders (`<your_username>`, `<set_a_temporary_password>`). |
| `apply_rbac.py` | Executes `rbac_and_governance.sql` programmatically, substituting the two placeholders from environment variables, so this step doesn't require manually pasting into Snowsight. |

## Required environment variables
Set these before running anything — **never hardcode credentials into any
file in this repo, never commit them, and never print them to logs**:

```bash
export SNOWFLAKE_ACCOUNT="ab12345.us-east-1"      # from the user's trial account
export SNOWFLAKE_USER="their_username"
export SNOWFLAKE_PASSWORD="their_password"
export SNOWFLAKE_ADMIN_USERNAME="their_username"  # usually same as SNOWFLAKE_USER
export DEMO_ANALYST_PASSWORD="<generate a random one if not given>"
```

If any of these are missing, **stop and ask the user** rather than guessing,
inventing a value, or proceeding with a placeholder.

## Run order (do not reorder)

1. **Check Python dependencies.** Run `pip show pandas numpy snowflake-connector-python`.
   If any are missing: `pip install pandas numpy snowflake-connector-python`.

2. **Generate the synthetic data.**
   ```bash
   python generate_data.py
   ```
   Confirm it prints `Total fact rows: 1569088`. If the number differs, stop
   and report it — don't proceed with a mismatched dataset.

3. **Create warehouse/schema/tables and load data.**
   ```bash
   python load_to_snowflake.py
   ```
   This is idempotent (`CREATE OR REPLACE`, `CREATE IF NOT EXISTS`) — safe to
   re-run if it fails partway. Confirm the final row-count printout shows:
   - `FACT_LOAN_SERVICING_EVENT: 1,569,088`
   - `DIM_LOAN: 25,000`
   - `DIM_BORROWER: 25,000`

   If `COPY INTO` reports load errors, read them — they'll name the file and
   row. Common cause: a `FILE_FORMAT` mismatch on date parsing. Fix the format
   clause, don't skip the failing rows silently.

4. **Apply RBAC and governance.**
   ```bash
   python apply_rbac.py
   ```
   This creates the three roles, the three analyst-facing views, the masking
   policy, and a second login (`MRCOOPER_DEMO_ANALYST`). It ends by printing
   5 real `synthetic_borrower_id` values as the Admin role, to confirm the
   base table still returns unmasked data for Admin/Engineer.

5. **Verify the masking actually works.** This is the step that proves the
   governance claim in the report, so don't skip it:
   - Open a *new* Snowsight worksheet (or reconnect) as `MRCOOPER_DEMO_ANALYST`.
   - Run `USE ROLE MTG_DATA_ANALYST;` then `SELECT * FROM VW_DELINQUENCY_TREND LIMIT 5;`
     — should succeed.
   - Run `SELECT * FROM DIM_BORROWER LIMIT 5;` — should **fail** with an
     access-denied error (no base-table grant for this role).
   - If a `synthetic_borrower_id` were exposed through a view, it should read
     `MASKED-ID`, not a real-looking value.
   - Report the actual outcome of each check back to the user — don't assume
     success without seeing the query result.

6. **Report back concrete evidence**, not just "done": the row counts from
   step 3, confirmation that all statements in step 4 succeeded (or which
   ones didn't and why), and the three verification results from step 5.
   This is what goes into the report as proof, so approximate or assumed
   results aren't good enough.

## What NOT to do
- Don't modify `generate_data.py`'s random seed or distributions — the Mid-
  Semester Report cites specific numbers (1,569,088 rows, 92.07% current
  delinquency, etc.) that depend on this exact generation logic matching.
- Don't load, reference, or substitute any real client, loan, or borrower
  data at any step.
- Don't edit the Mid-Semester Report `.docx`/`.pdf` as part of this task
  unless explicitly asked to — this folder's job is the Snowflake build only.
- Don't leave a warehouse running — confirm `AUTO_SUSPEND = 60` took effect
  (it's set in the DDL) rather than manually suspending after each run.
- If something fails and you're unsure why, say so — don't paper over a
  failed step with a plausible-sounding but unverified claim of success.
