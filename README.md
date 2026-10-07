# Mortgage-Servicing Snowflake PoC

Cloud data warehouse proof-of-concept for the BITS WILP MBA dissertation
*"The Role of Cloud Data Warehouses in Accelerating Self-Service Analytics
in Mortgage Servicing."*

Builds a Snowflake warehouse end-to-end: a star-schema data model, a fully
synthetic 1.57M-row mortgage-servicing dataset (fixed random seed, no real
loan/borrower/organizational data), and a three-role governance model
(Admin / Data Engineer / Data Analyst) with a masking policy on the
borrower identifier.

## Files

| File | Purpose |
|---|---|
| `generate_data.py` | Generates the 7 synthetic CSVs (6 dimensions + 1 fact, ~1.57M fact rows). Deterministic — fixed seed. |
| `load_to_snowflake.py` | Creates the warehouse/database/schema/tables and loads the CSVs via internal stage (`PUT` + `COPY INTO`). |
| `rbac_and_governance.sql` | Creates the three roles, grants, three semantic-layer views, and the masking policy on the borrower identifier. |
| `apply_rbac.py` | Executes `rbac_and_governance.sql` programmatically against the Snowflake account. |
| `MidSem.pdf` | Mid-Semester Project Report. |
| `MidSem_Presentation.html` | Self-contained interactive slide deck for the mid-semester presentation. |

## Setup

Set these environment variables (or fill in `.env` — never committed):

```
SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PASSWORD
SNOWFLAKE_ADMIN_USERNAME
DEMO_ANALYST_PASSWORD
```

Run in order:

```bash
python generate_data.py
python load_to_snowflake.py
python apply_rbac.py
```

No real client, loan, or borrower data is used anywhere in this project.
