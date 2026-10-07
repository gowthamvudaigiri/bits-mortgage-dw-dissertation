"""
Synthetic mortgage-servicing dataset generator.
Produces fully synthetic loans, borrowers, investors, servicers, dates,
delinquency buckets, and monthly servicing events (payment / escrow / remittance).
No real loan, borrower, or organizational data is used anywhere in this script.
"""
import numpy as np
import pandas as pd
import string

rng = np.random.default_rng(42)

N_LOANS = 25000
N_MONTHS = 24
START_YEAR, START_MONTH = 2024, 1

US_STATES = ["CA","TX","FL","NY","PA","OH","GA","NC","MI","AZ","WA","CO","VA","OR","TN"]
CREDIT_BANDS = ["<620","620-659","660-699","700-739","740-779","780+"]
INCOME_BANDS = ["<50K","50-75K","75-100K","100-150K","150K+"]
LOAN_TYPES = ["Fixed","ARM"]
PRODUCT_TYPES = ["Conventional","FHA","VA","Jumbo"]
TERMS = [180, 240, 360]
DPD_BUCKETS = [
    (0,    "Current (0 DPD)",   0.920),
    (1,    "1-30 DPD",          0.050),
    (2,    "31-60 DPD",         0.020),
    (3,    "61-90 DPD",         0.007),
    (4,    "90+ DPD",           0.003),
]
BUCKET_DPD_VALUE = {0:0, 1:15, 2:45, 3:75, 4:105}
BUCKET_LABEL = {b[0]: b[1] for b in DPD_BUCKETS}
BUCKET_PROB = [b[2] for b in DPD_BUCKETS]

INVESTORS = [
    ("Fannie Mae", "GSE"), ("Freddie Mac", "GSE"), ("Ginnie Mae", "GSE"),
    ("PL Trust Alpha", "Private-Label"), ("PL Trust Beta", "Private-Label"),
    ("PL Trust Gamma", "Private-Label"), ("PL Trust Delta", "Private-Label"),
    ("PL Trust Epsilon", "Private-Label"), ("PL Trust Zeta", "Private-Label"),
]
SERVICERS = [
    ("Branch-East", "East"), ("Branch-West", "West"),
    ("Branch-Central", "Central"), ("Branch-South", "South"),
]

def rand_id(n_digits, seed_offset):
    return np.array(["".join(rng.choice(list(string.digits), n_digits)) for _ in range(seed_offset)])

# ---------- DIM_DATE ----------
dates = pd.date_range(f"{START_YEAR}-{START_MONTH:02d}-01", periods=N_MONTHS, freq="MS")
dim_date = pd.DataFrame({
    "date_sk": range(1, len(dates) + 1),
    "calendar_date": dates,
    "month": dates.month,
    "quarter": dates.quarter,
    "year": dates.year,
})

# ---------- DIM_INVESTOR ----------
dim_investor = pd.DataFrame({
    "investor_sk": range(1, len(INVESTORS) + 1),
    "investor_name": [i[0] for i in INVESTORS],
    "investor_type": [i[1] for i in INVESTORS],
})

# ---------- DIM_SERVICER ----------
dim_servicer = pd.DataFrame({
    "servicer_sk": range(1, len(SERVICERS) + 1),
    "servicing_branch": [s[0] for s in SERVICERS],
    "region": [s[1] for s in SERVICERS],
})

# ---------- DIM_DELINQUENCY_BUCKET ----------
dim_bucket = pd.DataFrame({
    "bucket_sk": [b[0] for b in DPD_BUCKETS],
    "dpd_range": [BUCKET_DPD_VALUE[b[0]] for b in DPD_BUCKETS],
    "bucket_label": [b[1] for b in DPD_BUCKETS],
})

# ---------- DIM_LOAN ----------
origination = pd.to_datetime(
    rng.integers(pd.Timestamp("2014-01-01").value // 10**9,
                 pd.Timestamp("2023-12-31").value // 10**9,
                 N_LOANS), unit="s"
)
original_upb = rng.uniform(80000, 600000, N_LOANS).round(2)
interest_rate = rng.uniform(3.0, 8.0, N_LOANS).round(3)
dim_loan = pd.DataFrame({
    "loan_sk": range(1, N_LOANS + 1),
    "synthetic_loan_id": rand_id(10, N_LOANS),
    "origination_date": origination,
    "loan_type": rng.choice(LOAN_TYPES, N_LOANS, p=[0.8, 0.2]),
    "product_type": rng.choice(PRODUCT_TYPES, N_LOANS, p=[0.65, 0.15, 0.1, 0.1]),
    "original_upb": original_upb,
    "interest_rate": interest_rate,
    "term_months": rng.choice(TERMS, N_LOANS, p=[0.05, 0.15, 0.80]),
})

# ---------- DIM_BORROWER (1:1 with loan for this PoC) ----------
dim_borrower = pd.DataFrame({
    "borrower_sk": range(1, N_LOANS + 1),
    "synthetic_borrower_id": rand_id(12, N_LOANS),
    "state": rng.choice(US_STATES, N_LOANS),
    "credit_band": rng.choice(CREDIT_BANDS, N_LOANS, p=[0.05,0.10,0.20,0.25,0.25,0.15]),
    "income_band": rng.choice(INCOME_BANDS, N_LOANS, p=[0.15,0.25,0.25,0.20,0.15]),
})

import os
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

dim_loan.to_csv(os.path.join(OUT_DIR, "dim_loan.csv"), index=False)
dim_borrower.to_csv(os.path.join(OUT_DIR, "dim_borrower.csv"), index=False)
dim_date.to_csv(os.path.join(OUT_DIR, "dim_date.csv"), index=False)
dim_investor.to_csv(os.path.join(OUT_DIR, "dim_investor.csv"), index=False)
dim_servicer.to_csv(os.path.join(OUT_DIR, "dim_servicer.csv"), index=False)
dim_bucket.to_csv(os.path.join(OUT_DIR, "dim_delinquency_bucket.csv"), index=False)

# ---------- FACT_LOAN_SERVICING_EVENT ----------
investor_sk_for_loan = rng.integers(1, len(INVESTORS) + 1, N_LOANS)
servicer_sk_for_loan = rng.integers(1, len(SERVICERS) + 1, N_LOANS)
escrow_required = rng.random(N_LOANS) < 0.70
monthly_rate = interest_rate / 100.0 / 12.0

fact_rows = []
event_sk = 1
cur_upb = original_upb.copy()

for m_idx, date_sk in enumerate(dim_date["date_sk"].values):
    month_num = dim_date.loc[m_idx, "month"]
    bucket_sk = rng.choice([0,1,2,3,4], N_LOANS, p=BUCKET_PROB)
    dpd = np.array([BUCKET_DPD_VALUE[b] for b in bucket_sk])

    interest_amt = np.round(cur_upb * monthly_rate, 2)
    scheduled_amount = np.round(cur_upb * monthly_rate / (1 - (1+monthly_rate)**(-360)) , 2)
    scheduled_amount = np.nan_to_num(scheduled_amount, nan=0.0)
    principal_amt = np.round(np.clip(scheduled_amount - interest_amt, 0, None), 2)

    paid_mask = bucket_sk == 0
    actual_amount = np.where(paid_mask, scheduled_amount, 0.0)
    late_fee_amt = np.where(bucket_sk > 0, 25.0, 0.0)
    cur_upb = np.clip(cur_upb - np.where(paid_mask, principal_amt, 0.0), 0, None)

    # PAYMENT event (one row per loan per month)
    df_pay = pd.DataFrame({
        "event_sk": np.arange(event_sk, event_sk + N_LOANS),
        "loan_sk": dim_loan["loan_sk"].values,
        "date_sk": date_sk,
        "borrower_sk": dim_borrower["borrower_sk"].values,
        "investor_sk": investor_sk_for_loan,
        "servicer_sk": servicer_sk_for_loan,
        "bucket_sk": bucket_sk,
        "event_type": "PAYMENT",
        "scheduled_amount": scheduled_amount,
        "actual_amount": actual_amount,
        "principal_amt": np.where(paid_mask, principal_amt, 0.0),
        "interest_amt": np.where(paid_mask, interest_amt, 0.0),
        "escrow_amt": 0.0,
        "late_fee_amt": late_fee_amt,
        "days_past_due": dpd,
        "unpaid_principal_bal": cur_upb,
        "scheduled_remit_date": pd.NaT,
        "actual_remit_date": pd.NaT,
    })
    event_sk += N_LOANS
    fact_rows.append(df_pay)

    # ESCROW event (subset of loans, only if escrow_required)
    esc_idx = np.where(escrow_required)[0]
    n_esc = len(esc_idx)
    disb = rng.random(n_esc) < (1/6)
    escrow_amt = np.where(disb, -rng.uniform(1000, 1800, n_esc), rng.normal(200, 50, n_esc)).round(2)
    df_esc = pd.DataFrame({
        "event_sk": np.arange(event_sk, event_sk + n_esc),
        "loan_sk": dim_loan["loan_sk"].values[esc_idx],
        "date_sk": date_sk,
        "borrower_sk": dim_borrower["borrower_sk"].values[esc_idx],
        "investor_sk": investor_sk_for_loan[esc_idx],
        "servicer_sk": servicer_sk_for_loan[esc_idx],
        "bucket_sk": bucket_sk[esc_idx],
        "event_type": "ESCROW",
        "scheduled_amount": 0.0, "actual_amount": 0.0,
        "principal_amt": 0.0, "interest_amt": 0.0,
        "escrow_amt": escrow_amt, "late_fee_amt": 0.0,
        "days_past_due": dpd[esc_idx],
        "unpaid_principal_bal": cur_upb[esc_idx],
        "scheduled_remit_date": pd.NaT, "actual_remit_date": pd.NaT,
    })
    event_sk += n_esc
    fact_rows.append(df_esc)

    # REMITTANCE event (all loans, only when payment was actually collected)
    rem_idx = np.where(paid_mask)[0]
    n_rem = len(rem_idx)
    sched_date = pd.Timestamp(dim_date.loc[m_idx, "calendar_date"]) + pd.Timedelta(days=14)
    delay_days = rng.choice([0,1,2,3,4,5,10,15], n_rem, p=[0.35,0.20,0.15,0.10,0.08,0.07,0.03,0.02])
    actual_date = sched_date + pd.to_timedelta(delay_days, unit="D")
    df_rem = pd.DataFrame({
        "event_sk": np.arange(event_sk, event_sk + n_rem),
        "loan_sk": dim_loan["loan_sk"].values[rem_idx],
        "date_sk": date_sk,
        "borrower_sk": dim_borrower["borrower_sk"].values[rem_idx],
        "investor_sk": investor_sk_for_loan[rem_idx],
        "servicer_sk": servicer_sk_for_loan[rem_idx],
        "bucket_sk": bucket_sk[rem_idx],
        "event_type": "REMITTANCE",
        "scheduled_amount": 0.0, "actual_amount": 0.0,
        "principal_amt": principal_amt[rem_idx], "interest_amt": interest_amt[rem_idx],
        "escrow_amt": 0.0, "late_fee_amt": 0.0,
        "days_past_due": dpd[rem_idx],
        "unpaid_principal_bal": cur_upb[rem_idx],
        "scheduled_remit_date": sched_date,
        "actual_remit_date": actual_date,
    })
    event_sk += n_rem
    fact_rows.append(df_rem)

fact = pd.concat(fact_rows, ignore_index=True)
fact.to_csv(os.path.join(OUT_DIR, "fact_loan_servicing_event.csv"), index=False)

print("Loans:", len(dim_loan))
print("Months:", len(dim_date))
print("Total fact rows:", len(fact))
print(fact["event_type"].value_counts())
