import pandas as pd
from pathlib import Path
import calendar

# script: energy-eu-project/scripts/aggregation/clean_energy_load_aggregation.py
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]        # aggregation -> scripts -> project root
DATA_DIR = PROJECT_ROOT / "data" / "processed"

INPUT = DATA_DIR / "clean_energy_load.csv"

# IMPORTANT: overwrite old files
OUT_DAILY = DATA_DIR / "daily_load-2.csv"
OUT_MONTHLY = DATA_DIR / "monthly_load.csv"

CHUNK_SIZE = 500_000  # tune for RAM

daily_chunks = []

read_cols = ["timestamp", "country", "load"]
dtypes = {"country": "category", "load": "float32"}

for chunk in pd.read_csv(
    INPUT,
    usecols=read_cols,
    dtype=dtypes,
    parse_dates=["timestamp"],
    chunksize=CHUNK_SIZE,
):
    # Derive date for grouping
    chunk["date"] = chunk["timestamp"].dt.date

    # Daily aggregation for this chunk, including hours_count
    daily_agg = (
        chunk
        .groupby(["country", "date"], observed=True)
        .agg(
            load_sum=("load", "sum"),
            load_peak=("load", "max"),
            hours_count=("load", "size"),  # number of hourly records in this chunk
        )
        .reset_index()
    )
    daily_chunks.append(daily_agg)

# Combine all chunk results and aggregate again to get full-day stats
daily_all = pd.concat(daily_chunks, ignore_index=True)

daily_final = (
    daily_all
    .groupby(["country", "date"], observed=True)
    .agg(
        load_sum=("load_sum", "sum"),
        load_peak=("load_peak", "max"),
        hours_count=("hours_count", "sum"),
    )
    .reset_index()
)

# Compute load_mean from load_sum and hours_count
daily_final["load_mean"] = daily_final["load_sum"] / daily_final["hours_count"]

# Keep only full 24‑hour days
daily_full = daily_final.loc[daily_final["hours_count"] == 24].copy()

# Optional: print how many partial days were dropped per country
dropped = (
    daily_final.groupby("country")["date"].count()
    - daily_full.groupby("country")["date"].count()
)
print("Dropped partial days per country (approx):")
print(dropped.fillna(0).astype(int).sort_values(ascending=False).head(20))

# Save cleaned daily file, overwriting old one
daily_full.to_csv(OUT_DAILY, index=False)

# ---- Build monthly aggregates from cleaned daily data ----

daily_full["date"] = pd.to_datetime(daily_full["date"])
daily_full["year_month"] = daily_full["date"].values.astype("datetime64[M]")

monthly = (
    daily_full
    .groupby(["country", "year_month"], observed=True)
    .agg(
        load_sum=("load_sum", "sum"),
        load_peak=("load_peak", "max"),
        days_used=("date", "nunique"),
    )
    .reset_index()
)

# monthly mean = sum / (24 * number of full days)
monthly["load_mean"] = monthly["load_sum"] / (24 * monthly["days_used"])

# Overwrite old monthly file
monthly.to_csv(OUT_MONTHLY, index=False)