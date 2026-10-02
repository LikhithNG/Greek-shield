# Greek Shield (v1 — archived)

> **This is the first version of Greek Shield.** Active development continues in
> **[New-Greek-shield-](https://github.com/LikhithNG/New-Greek-shield-)**.

An options-risk data pipeline: pulls AAPL option chains with `yfinance`, stages them in **AWS S3**, and loads them into **Snowflake** (`OPTIONS_RISK_DB.RAW_DATA`) for Greeks and risk analysis, with a local CSV fallback in `data/`.

## Scripts

| Script | Purpose |
|---|---|
| `fetch_to_s3.py` | Fetch option chain from Yahoo Finance and upload JSON/CSV to S3 |
| `load_csv_to_snowflake.py`, `final_load.py`, `fix_and_load.py` | Load CSV snapshots into Snowflake |
| `automated_daily_pipeline.py`, `run_daily.py`, `run_scheduler.py`, `auto_scheduler.py` | Daily end-to-end run and scheduling |
| `pipeline_local.py`, `robust_pipeline.py` | Local/CSV-only pipeline variants |
| `generate_sample_data.py` | Generate sample option data |
| `connection.py`, `test_connection.py`, `test_s3.py`, `test_yfinance_fix.py` | Connectivity checks |

## Setup

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Snowflake and AWS values
python test_connection.py
python automated_daily_pipeline.py
```

Credentials are read only from environment variables (`.env`); never commit real values.
