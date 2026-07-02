import pandas as pd
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]  # aggregation -> scripts -> project root
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "eurostat"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INPUT = RAW_DIR / "estat_nrg_cb_pem_en.csv"
OUTPUT_MONTHLY = PROCESSED_DIR / "renewable_share_eurostat_monthly.csv"
OUTPUT_ANNUAL = PROCESSED_DIR / "renewable_share_eurostat_annual.csv"

# Countries in the project (match country_totals-9.csv)
PROJECT_COUNTRIES = [
    "AL", "AT", "BA", "BE", "BG", "CH", "CY", "CZ", "DE", "DK",
    "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE", "IS", "IT",
    "LT", "LU", "LV", "MD", "ME", "MK", "MT", "NL", "NO", "PL",
    "PT", "RO", "RS", "SE", "SI", "SK", "TR",
]

# Project → Eurostat geo code mapping (only GR↔EL differs)
EUROSTAT_GEO_MAP = {
    "GR": "EL",
}
INVERSE_GEO_MAP = {v: k for k, v in EUROSTAT_GEO_MAP.items()}

# Time window to match other datasets
START_PERIOD = "2015-01"
END_PERIOD = "2024-12"

# SIEC codes we care about: renewables+biofuels and total generation
KEEP_SIEC = ["RA000", "TOTAL"]


def read_eurostat_file(path: Path) -> pd.DataFrame:
    """Read raw Eurostat nrg_cb_pem and filter to the project’s scope."""
    df = pd.read_csv(path, low_memory=False)

    # Keep only monthly GWh observations for renewable generation and total generation
    df = df[(df["freq"] == "M") & (df["unit"] == "GWH")].copy()
    df = df[df["siec"].isin(KEEP_SIEC)].copy()

    # Harmonise project country codes to Eurostat codes for filtering
    eurostat_countries = [EUROSTAT_GEO_MAP.get(c, c) for c in PROJECT_COUNTRIES]
    df = df[df["geo"].isin(eurostat_countries)].copy()

    # Ensure numeric values and valid monthly periods
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE", "TIME_PERIOD"])

    df["TIME_PERIOD"] = df["TIME_PERIOD"].astype(str)
    df = df[df["TIME_PERIOD"].str.match(r"^\d{4}-\d{2}$", na=False)].copy()

    # Normalise to the project time window used by the other datasets
    df = df[(df["TIME_PERIOD"] >= START_PERIOD) & (df["TIME_PERIOD"] <= END_PERIOD)].copy()

    # Convert Eurostat geo codes back to project codes
    df["geo"] = df["geo"].replace(INVERSE_GEO_MAP)

    return df


def build_monthly_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Build a full monthly panel for all project countries from 2015-01 to 2024-12."""
    monthly = (
        df.pivot_table(
            index=["geo", "TIME_PERIOD"],
            columns="siec",
            values="OBS_VALUE",
            aggfunc="sum",
        )
        .reset_index()
    )
    monthly.columns.name = None

    # Ensure columns exist even if some codes are missing for some countries/periods
    if "RA000" not in monthly.columns:
        monthly["RA000"] = pd.NA
    if "TOTAL" not in monthly.columns:
        monthly["TOTAL"] = pd.NA

    monthly = monthly.rename(
        columns={
            "geo": "country",
            "TIME_PERIOD": "time_period",
            "RA000": "renewable_generation_gwh",
            "TOTAL": "total_generation_gwh",
        }
    )

    # Build a full monthly panel so all project countries have 2015-01 to 2024-12
    months = pd.period_range(START_PERIOD, END_PERIOD, freq="M").astype(str)
    full_index = pd.MultiIndex.from_product(
        [PROJECT_COUNTRIES, months], names=["country", "time_period"]
    )
    full = pd.DataFrame(index=full_index).reset_index()

    monthly = full.merge(monthly, on=["country", "time_period"], how="left")

    monthly["year"] = monthly["time_period"].str.slice(0, 4).astype(int)
    monthly["month"] = monthly["time_period"].str.slice(5, 7).astype(int)
    monthly["renewable_share"] = (
        monthly["renewable_generation_gwh"] / monthly["total_generation_gwh"]
    )

    monthly = monthly[
        [
            "country",
            "time_period",
            "year",
            "month",
            "renewable_generation_gwh",
            "total_generation_gwh",
            "renewable_share",
        ]
    ].sort_values(["country", "time_period"])

    return monthly


def build_annual_panel(monthly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the normalised monthly panel to annual country-year figures."""
    annual = (
        monthly.groupby(["country", "year"], as_index=False)[
            ["renewable_generation_gwh", "total_generation_gwh"]
        ]
        .sum(min_count=1)
    )
    annual["renewable_share"] = (
        annual["renewable_generation_gwh"] / annual["total_generation_gwh"]
    )
    annual = annual.sort_values(["country", "year"])
    return annual


def main():
    if not INPUT.exists():
        raise RuntimeError(f"Eurostat raw file not found: {INPUT}")

    df = read_eurostat_file(INPUT)
    monthly = build_monthly_panel(df)
    annual = build_annual_panel(monthly)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(OUTPUT_MONTHLY, index=False)
    annual.to_csv(OUTPUT_ANNUAL, index=False)

    print(f"Wrote {OUTPUT_MONTHLY} with {len(monthly)} rows")
    print(f"Wrote {OUTPUT_ANNUAL} with {len(annual)} rows")


if __name__ == "__main__":
    main()