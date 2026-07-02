import pandas as pd
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]  # aggregation -> scripts -> project root
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "eurostat"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INPUT = RAW_DIR / "estat_nrg_cb_pem_en.csv"
OUTPUT_MONTHLY = PROCESSED_DIR / "eurostat_generation_by_fuel_monthly.csv"
OUTPUT_ANNUAL = PROCESSED_DIR / "eurostat_generation_by_fuel_annual.csv"

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

START_PERIOD = "2015-01"
END_PERIOD = "2024-12"

# Fuel / product codes (SIEC) we care about
KEEP_SIEC = [
    "TOTAL",      # total net electricity generation
    "RA000",      # renewables and biofuels (aggregate)
    "RA100", "RA110", "RA120", "RA130",  # hydro breakdown
    "RA200",      # geothermal
    "RA300", "RA310", "RA320",           # wind (total / onshore / offshore)
    "RA400", "RA410", "RA420",           # solar (total / thermal / PV)
    "RA500_5160", # other renewable energies
    "CF", "CF_R", "CF_NR_OTH",          # combustible fuels
    "C0000",      # coal and manufactured gases
    "G3000",      # natural gas
    "O4000XBIO",  # oil and petroleum products (excl. biofuel portion)
    "FE",         # fossil energy
    "N9000",      # nuclear + other fuels n.e.c.
    "X9900",      # other fuels n.e.c.
]


def read_eurostat_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)

    # Keep only monthly GWh observations for selected fuel codes
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


def build_monthly_by_fuel(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly panel with one column per fuel code plus total."""
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

    # Ensure all requested SIEC columns exist
    for code in KEEP_SIEC:
        if code not in monthly.columns:
            monthly[code] = pd.NA

    monthly = monthly.rename(columns={"geo": "country", "TIME_PERIOD": "time_period"})

    # Build a full monthly panel so all project countries have 2015-01 to 2024-12
    months = pd.period_range(START_PERIOD, END_PERIOD, freq="M").astype(str)
    full_index = pd.MultiIndex.from_product(
        [PROJECT_COUNTRIES, months], names=["country", "time_period"]
    )
    full = pd.DataFrame(index=full_index).reset_index()

    monthly = full.merge(monthly, on=["country", "time_period"], how="left")

    monthly["year"] = monthly["time_period"].str.slice(0, 4).astype(int)
    monthly["month"] = monthly["time_period"].str.slice(5, 7).astype(int)

    # Optional: per-fuel shares in total generation
    if "TOTAL" in monthly.columns:
        total = monthly["TOTAL"]
        for code in KEEP_SIEC:
            if code == "TOTAL":
                continue
            share_col = f"share_{code.lower()}"
            monthly[share_col] = monthly[code] / total

    monthly = monthly.sort_values(["country", "time_period"])
    return monthly


def build_annual_by_fuel(monthly: pd.DataFrame) -> pd.DataFrame:
    """Annual aggregation by country-year and fuel code."""
    value_cols = KEEP_SIEC.copy()
    # Keep only columns that actually exist in monthly
    value_cols = [c for c in value_cols if c in monthly.columns]

    annual = (
        monthly.groupby(["country", "year"], as_index=False)[value_cols]
        .sum(min_count=1)
    )

    # Optional per-fuel annual shares
    if "TOTAL" in annual.columns:
        total = annual["TOTAL"]
        for code in KEEP_SIEC:
            if code == "TOTAL":
                continue
            if code in annual.columns:
                share_col = f"share_{code.lower()}"
                annual[share_col] = annual[code] / total

    annual = annual.sort_values(["country", "year"])
    return annual


def main():
    if not INPUT.exists():
        raise RuntimeError(f"Eurostat raw file not found: {INPUT}")

    df = read_eurostat_file(INPUT)
    monthly = build_monthly_by_fuel(df)
    annual = build_annual_by_fuel(monthly)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(OUTPUT_MONTHLY, index=False)
    annual.to_csv(OUTPUT_ANNUAL, index=False)

    print(f"Wrote {OUTPUT_MONTHLY} with {len(monthly)} rows")
    print(f"Wrote {OUTPUT_ANNUAL} with {len(annual)} rows")


if __name__ == "__main__":
    main()