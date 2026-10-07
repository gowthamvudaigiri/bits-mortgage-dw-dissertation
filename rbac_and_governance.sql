-- ============================================================
-- Run this in a Snowsight worksheet AFTER load_to_snowflake.py
-- has finished, using the ACCOUNTADMIN role (default for a
-- trial account owner).
-- ============================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE MTG_ANALYTICS_WH;
USE DATABASE MTG_SERVICING_DW;
USE SCHEMA CORE;

-- ---------- A5.2 Roles and role hierarchy ----------
CREATE ROLE IF NOT EXISTS MTG_DW_ADMIN;
CREATE ROLE IF NOT EXISTS MTG_DATA_ENGINEER;
CREATE ROLE IF NOT EXISTS MTG_DATA_ANALYST;

GRANT ROLE MTG_DATA_ENGINEER TO ROLE MTG_DW_ADMIN;
GRANT ROLE MTG_DATA_ANALYST  TO ROLE MTG_DW_ADMIN;
-- Let your own trial-account user hold the admin and engineer roles so you can test everything:
-- (replace <your_username> with your real username)
GRANT ROLE MTG_DW_ADMIN TO USER <your_username>;
GRANT ROLE MTG_DATA_ENGINEER TO USER <your_username>;

GRANT USAGE ON WAREHOUSE MTG_ANALYTICS_WH TO ROLE MTG_DW_ADMIN;
GRANT USAGE ON WAREHOUSE MTG_ANALYTICS_WH TO ROLE MTG_DATA_ENGINEER;
GRANT USAGE ON WAREHOUSE MTG_ANALYTICS_WH TO ROLE MTG_DATA_ANALYST;
GRANT USAGE ON DATABASE MTG_SERVICING_DW TO ROLE MTG_DW_ADMIN;
GRANT USAGE ON DATABASE MTG_SERVICING_DW TO ROLE MTG_DATA_ENGINEER;
GRANT USAGE ON DATABASE MTG_SERVICING_DW TO ROLE MTG_DATA_ANALYST;
GRANT USAGE ON SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DW_ADMIN;
GRANT USAGE ON SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DATA_ENGINEER;
GRANT USAGE ON SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DATA_ANALYST;

-- ---------- A5.3 Admin — full control ----------
GRANT ALL ON SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DW_ADMIN;
GRANT ALL ON ALL TABLES IN SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DW_ADMIN;
GRANT ALL ON FUTURE TABLES IN SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DW_ADMIN;

-- ---------- A5.4 Data Engineer — build and load ----------
GRANT CREATE TABLE, CREATE VIEW ON SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DATA_ENGINEER;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
  ON ALL TABLES IN SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DATA_ENGINEER;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
  ON FUTURE TABLES IN SCHEMA MTG_SERVICING_DW.CORE TO ROLE MTG_DATA_ENGINEER;

-- ---------- A5.5 Semantic layer — analyst-facing views ----------
CREATE OR REPLACE VIEW VW_DELINQUENCY_TREND AS
SELECT d.year, d.month, b.state, k.bucket_label,
       COUNT(DISTINCT f.loan_sk) AS loan_count,
       SUM(f.unpaid_principal_bal) AS total_upb
FROM FACT_LOAN_SERVICING_EVENT f
JOIN DIM_DATE d ON f.date_sk = d.date_sk
JOIN DIM_BORROWER b ON f.borrower_sk = b.borrower_sk
JOIN DIM_DELINQUENCY_BUCKET k ON f.bucket_sk = k.bucket_sk
WHERE f.event_type = 'PAYMENT'
GROUP BY d.year, d.month, b.state, k.bucket_label;

CREATE OR REPLACE VIEW VW_ESCROW_POSITION AS
SELECT l.synthetic_loan_id, SUM(f.escrow_amt) AS net_escrow_position
FROM FACT_LOAN_SERVICING_EVENT f
JOIN DIM_LOAN l ON f.loan_sk = l.loan_sk
WHERE f.event_type = 'ESCROW'
GROUP BY l.synthetic_loan_id;

CREATE OR REPLACE VIEW VW_REMITTANCE_TIMELINESS AS
SELECT i.investor_name,
       AVG(DATEDIFF('day', f.scheduled_remit_date, f.actual_remit_date)) AS avg_delay_days,
       COUNT(*) AS remittance_count
FROM FACT_LOAN_SERVICING_EVENT f
JOIN DIM_INVESTOR i ON f.investor_sk = i.investor_sk
WHERE f.event_type = 'REMITTANCE'
GROUP BY i.investor_name;

-- ---------- A5.6 Data Analyst — read-only via views, plus masking ----------
GRANT SELECT ON VIEW VW_DELINQUENCY_TREND     TO ROLE MTG_DATA_ANALYST;
GRANT SELECT ON VIEW VW_ESCROW_POSITION       TO ROLE MTG_DATA_ANALYST;
GRANT SELECT ON VIEW VW_REMITTANCE_TIMELINESS TO ROLE MTG_DATA_ANALYST;
-- Note: MTG_DATA_ANALYST is NOT granted SELECT on the base tables directly.

CREATE OR REPLACE MASKING POLICY MASK_BORROWER_ID AS (val VARCHAR) RETURNS VARCHAR ->
  CASE
    WHEN CURRENT_ROLE() IN ('MTG_DW_ADMIN', 'MTG_DATA_ENGINEER') THEN val
    ELSE 'MASKED-ID'
  END;

ALTER TABLE DIM_BORROWER
  MODIFY COLUMN synthetic_borrower_id
  SET MASKING POLICY MASK_BORROWER_ID;

-- ---------- A5.7 Create a second user to test the Analyst role ----------
-- (Trial accounts can create additional users under ACCOUNTADMIN.)
CREATE USER IF NOT EXISTS MRCOOPER_DEMO_ANALYST
  PASSWORD = '<set_a_temporary_password>'
  DEFAULT_ROLE = MTG_DATA_ANALYST
  DEFAULT_WAREHOUSE = MTG_ANALYTICS_WH
  DEFAULT_NAMESPACE = MTG_SERVICING_DW.CORE
  MUST_CHANGE_PASSWORD = TRUE;
GRANT ROLE MTG_DATA_ANALYST TO USER MRCOOPER_DEMO_ANALYST;

-- ---------- Verification ----------
-- Run as yourself (ADMIN) — should see the real synthetic_borrower_id:
USE ROLE MTG_DW_ADMIN;
SELECT TOP 5 synthetic_borrower_id FROM DIM_BORROWER;

-- Then log in as MRCOOPER_DEMO_ANALYST (or run `USE ROLE MTG_DATA_ANALYST;` in a
-- new worksheet) and run the same query against the view — the identifier
-- column will show as 'MASKED-ID' instead of the real synthetic value:
-- USE ROLE MTG_DATA_ANALYST;
-- SELECT * FROM VW_DELINQUENCY_TREND LIMIT 5;
