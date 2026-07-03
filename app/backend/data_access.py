import pandas as pd
from pathlib import Path

# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]                  # backend -> app -> project root
DATA_DIR = PROJECT_ROOT / "data" / "processed"

# ENTSO-E / load
DAILY_PATH = DATA_DIR / "daily_load-2.csv"
MONTHLY_PATH = DATA_DIR / "monthly_load.csv"
CLEAN_HOURLY_PATH = DATA_DIR / "clean_energy_load.csv"

# ENTSO-E / flows
FLOW_ENERGY_PATH = DATA_DIR / "energy_flows.csv"
FLOW_MONTHLY_PATH = DATA_DIR / "monthly_flows.csv"
FLOW_TOTAL_PATH = DATA_DIR / "flows_total.csv"
COUNTRY_TOTALS_PATH = DATA_DIR / "country_totals.csv"

# ENTSO-E / net generation capacity
NGC_PATH = DATA_DIR / "net_generation_capacity.csv"

# Eurostat / aggregated renewables
EUROSTAT_SHARE_ANNUAL_PATH = DATA_DIR / "renewable_share_eurostat_annual.csv"
EUROSTAT_FUEL_ANNUAL_PATH = DATA_DIR / "eurostat_generation_by_fuel_annual.csv"

# --------------------------------------------------------------------
# Cached dataframes
# --------------------------------------------------------------------

_daily_df = None
_monthly_df = None
_energy_flows_df = None
_monthly_flows_df = None
_flow_totals_df = None
_country_totals_df = None
_ngc_df = None
_eu_share_annual_df = None
_eu_fuel_annual_df = None

# --------------------------------------------------------------------
# Load / demand
# --------------------------------------------------------------------

def load_daily():
    global _daily_df
    if _daily_df is None:
        _daily_df = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    return _daily_df


def load_monthly():
    global _monthly_df
    if _monthly_df is None:
        _monthly_df = pd.read_csv(MONTHLY_PATH, parse_dates=["year_month"])
    return _monthly_df


def get_daily_load(country: str, start_date, end_date):
    df = load_daily()
    mask = (
        (df["country"] == country)
        & (df["date"] >= pd.to_datetime(start_date))
        & (df["date"] <= pd.to_datetime(end_date))
    )
    return df.loc[mask].sort_values("date")


def get_monthly_load(country: str, start_month, end_month):
    df = load_monthly()
    mask = (
        (df["country"] == country)
        & (df["year_month"] >= pd.to_datetime(start_month))
        & (df["year_month"] <= pd.to_datetime(end_month))
    )
    return df.loc[mask].sort_values("year_month")


def get_annual_load(country: str):
    """
    Aggregate monthly load to annual totals for a given country.
    """
    df = load_monthly()
    df_country = df.loc[df["country"] == country].copy()

    if df_country.empty:
        return pd.DataFrame(columns=["year", "annual_load_mwh"])

    df_country["year"] = df_country["year_month"].dt.year

    annual = (
        df_country.groupby("year", observed=True)["load_sum"]
        .sum()
        .reset_index()
        .rename(columns={"load_sum": "annual_load_mwh"})
        .sort_values("year")
    )
    return annual

# --------------------------------------------------------------------
# Hourly load
# --------------------------------------------------------------------

def get_hourly_load_window(country: str, start_ts, end_ts):
    """
    Return hourly load for a given country in a small time window.
    WARNING: clean_energy_load.csv is huge, so only use for short ranges.
    """
    start_ts = pd.to_datetime(start_ts)
    end_ts = pd.to_datetime(end_ts)

    chunks = []
    read_cols = ["timestamp", "country", "load"]
    dtypes = {"country": "category", "load": "float32"}

    for chunk in pd.read_csv(
        CLEAN_HOURLY_PATH,
        usecols=read_cols,
        dtype=dtypes,
        parse_dates=["timestamp"],
        chunksize=500_000,
    ):
        mask = (
            (chunk["country"] == country)
            & (chunk["timestamp"] >= start_ts)
            & (chunk["timestamp"] <= end_ts)
        )
        filtered = chunk.loc[mask]
        if not filtered.empty:
            chunks.append(filtered)

    if not chunks:
        return pd.DataFrame(columns=["timestamp", "country", "load"])

    return pd.concat(chunks, ignore_index=True).sort_values("timestamp")


def get_intraday_profile(country: str, start_ts, end_ts):
    df = get_hourly_load_window(country, start_ts, end_ts)
    if df.empty:
        return df

    df["hour"] = df["timestamp"].dt.hour

    profile = (
        df.groupby("hour", observed=True)["load"]
        .agg(["mean", "max"])
        .reset_index()
        .rename(columns={"mean": "load_mean", "max": "load_peak"})
        .sort_values("hour")
    )
    return profile

# --------------------------------------------------------------------
# Flows
# --------------------------------------------------------------------

def load_energy_flows():
    global _energy_flows_df
    if _energy_flows_df is None:
        _energy_flows_df = pd.read_csv(FLOW_ENERGY_PATH, parse_dates=["date"])
    return _energy_flows_df


def load_monthly_flows():
    global _monthly_flows_df
    if _monthly_flows_df is None:
        _monthly_flows_df = pd.read_csv(FLOW_MONTHLY_PATH, parse_dates=["date"])
    return _monthly_flows_df


def load_flow_totals():
    global _flow_totals_df
    if _flow_totals_df is None:
        _flow_totals_df = pd.read_csv(FLOW_TOTAL_PATH)
    return _flow_totals_df


def load_country_totals():
    global _country_totals_df
    if _country_totals_df is None:
        _country_totals_df = pd.read_csv(COUNTRY_TOTALS_PATH)
    return _country_totals_df


def get_net_country_flows(country: str, start_month, end_month):
    df = load_energy_flows()
    mask = (
        (df["country"] == country)
        & (df["date"] >= pd.to_datetime(start_month))
        & (df["date"] <= pd.to_datetime(end_month))
    )
    grouped = (
        df.loc[mask]
        .groupby("date", observed=True)["flow_signed"]
        .sum()
        .reset_index()
        .rename(columns={"flow_signed": "net_flow"})
        .sort_values("date")
    )
    return grouped


def get_monthly_border_flows(country: str, partner: str, start_month, end_month):
    df = load_monthly_flows()
    mask = (
        (df["country"] == country)
        & (df["partner"] == partner)
        & (df["date"] >= pd.to_datetime(start_month))
        & (df["date"] <= pd.to_datetime(end_month))
    )
    return df.loc[mask].sort_values("date")


def get_country_totals():
    return load_country_totals()


def get_total_border_flows():
    return load_flow_totals()


def get_border_partners(country: str):
    df = load_flow_totals()
    partners = (
        df.loc[df["country"] == country, "partner"]
        .dropna()
        .unique()
    )
    return sorted(partners)

# --------------------------------------------------------------------
# Net generation capacity
# --------------------------------------------------------------------

def load_ngc():
    global _ngc_df
    if _ngc_df is None:
        _ngc_df = pd.read_csv(NGC_PATH)
    return _ngc_df


def get_renewable_capacity(country: str):
    df = load_ngc()
    mask = (df["country"] == country) & (df["is_renewable"])
    out = (
        df.loc[mask]
        .groupby("year", observed=True)["capacity_mw"]
        .sum()
        .reset_index()
        .rename(columns={"capacity_mw": "renewable_capacity_mw"})
        .sort_values("year")
    )
    return out


def get_total_capacity(country: str):
    df = load_ngc()
    mask = df["country"] == country
    out = (
        df.loc[mask]
        .groupby("year", observed=True)["capacity_mw"]
        .sum()
        .reset_index()
        .rename(columns={"capacity_mw": "total_capacity_mw"})
        .sort_values("year")
    )
    return out


def get_renewable_share(country: str):
    """
    Capacity-based renewable share (ENTSO-E).
    """
    df_ren = get_renewable_capacity(country)
    df_tot = get_total_capacity(country)

    if df_ren.empty or df_tot.empty:
        return pd.DataFrame(
            columns=["year", "renewable_capacity_mw", "total_capacity_mw", "renewable_share"]
        )

    merged = df_ren.merge(df_tot, on="year", how="inner")
    merged["renewable_share"] = (
        merged["renewable_capacity_mw"] / merged["total_capacity_mw"]
    )
    return merged.sort_values("year").reset_index(drop=True)


def get_renewable_by_category(country: str):
    df = load_ngc()
    mask = (df["country"] == country) & (df["is_renewable"])
    out = (
        df.loc[mask]
        .groupby(["year", "category"], observed=True)["capacity_mw"]
        .sum()
        .reset_index()
        .sort_values(["year", "category"])
    )
    return out


def get_ngc_year_bounds():
    df = load_ngc()
    return int(df["year"].min()), int(df["year"].max())


def get_capacity_vs_load(country: str):
    """
    Combine renewable/total capacity with annual load for a country.
    """
    df_cap = get_renewable_share(country)
    df_load = get_annual_load(country)

    if df_cap.empty or df_load.empty:
        return pd.DataFrame(
            columns=[
                "year",
                "renewable_capacity_mw",
                "total_capacity_mw",
                "renewable_share",
                "annual_load_mwh",
                "load_per_mw",
            ]
        )

    merged = df_cap.merge(df_load, on="year", how="inner")
    merged["load_per_mw"] = merged["annual_load_mwh"] / merged["total_capacity_mw"]
    return merged.sort_values("year").reset_index(drop=True)

# --------------------------------------------------------------------
# Eurostat aggregated renewables
# --------------------------------------------------------------------

def load_eurostat_share_annual():
    """
    renewable_share_eurostat_annual.csv:
    country, year, renewable_generation_gwh, total_generation_gwh, renewable_share
    """
    global _eu_share_annual_df
    if _eu_share_annual_df is None:
        _eu_share_annual_df = pd.read_csv(EUROSTAT_SHARE_ANNUAL_PATH)
    return _eu_share_annual_df


def load_eurostat_generation_by_fuel_annual():
    """
    eurostat_generation_by_fuel_annual.csv:
    country, year, TOTAL, RA000, RA100, ..., plus optional share_* columns
    """
    global _eu_fuel_annual_df
    if _eu_fuel_annual_df is None:
        _eu_fuel_annual_df = pd.read_csv(EUROSTAT_FUEL_ANNUAL_PATH)
    return _eu_fuel_annual_df


def get_generation_share(country: str):
    """
    Annual renewable generation share (Eurostat).
    """
    df = load_eurostat_share_annual()
    df = df[df["country"] == country].copy()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "country",
                "year",
                "renewable_generation_gwh",
                "total_generation_gwh",
                "renewable_share",
            ]
        )

    return df.sort_values("year").reset_index(drop=True)


def get_generation_year_bounds():
    df = load_eurostat_share_annual().copy()
    df = df.dropna(subset=["renewable_generation_gwh", "total_generation_gwh"])
    return int(df["year"].min()), int(df["year"].max())


# --------------------------------------------------------------------
# Seasonality decomposition
# --------------------------------------------------------------------

def get_seasonal_decomposition(country: str, start_month=None, end_month=None):
    """
    Perform STL (Seasonal-Trend using LOESS) decomposition on monthly load data.

    Returns a DataFrame with columns:
        year_month, load_sum, trend, seasonal, residual, seasonal_strength
    """
    from statsmodels.tsa.seasonal import STL

    df = load_monthly()
    df_c = df.loc[df["country"] == country].copy().sort_values("year_month")

    if start_month is not None:
        df_c = df_c[df_c["year_month"] >= pd.to_datetime(start_month)]
    if end_month is not None:
        df_c = df_c[df_c["year_month"] <= pd.to_datetime(end_month)]

    if len(df_c) < 24:
        # Need at least 2 full years for meaningful decomposition
        return pd.DataFrame(
            columns=["year_month", "load_sum", "trend", "seasonal", "residual"]
        )

    # Set datetime index for STL
    series = df_c.set_index("year_month")["load_sum"]
    series.index = pd.DatetimeIndex(series.index, freq="MS")

    # STL decomposition with period=12 (monthly data, annual cycle)
    stl = STL(series, period=12, robust=True)
    result = stl.fit()

    out = pd.DataFrame(
        {
            "year_month": series.index,
            "load_sum": series.values,
            "trend": result.trend,
            "seasonal": result.seasonal,
            "residual": result.resid,
        }
    )

    return out.reset_index(drop=True)


def get_seasonal_strength(country: str, start_month=None, end_month=None):
    """
    Compute seasonal strength metric: 1 - Var(residual) / Var(seasonal + residual)
    Values close to 1 mean strong seasonality; close to 0 mean weak.
    """
    df = get_seasonal_decomposition(country, start_month, end_month)

    if df.empty:
        return None

    var_resid = df["residual"].var()
    var_seasonal_resid = (df["seasonal"] + df["residual"]).var()

    if var_seasonal_resid == 0:
        return 0.0

    strength = max(0, 1 - var_resid / var_seasonal_resid)
    return round(strength, 3)


def get_anomaly_months(country: str, start_month=None, end_month=None, threshold: float = 2.0):
    """
    Identify months where the residual exceeds `threshold` standard deviations.
    These are anomalies — unexpected deviations from trend + season.

    Returns DataFrame with: year_month, load_sum, residual, residual_zscore
    """
    df = get_seasonal_decomposition(country, start_month, end_month)

    if df.empty:
        return pd.DataFrame(columns=["year_month", "load_sum", "residual", "residual_zscore"])

    mean_r = df["residual"].mean()
    std_r = df["residual"].std()

    if std_r == 0:
        df["residual_zscore"] = 0.0
    else:
        df["residual_zscore"] = (df["residual"] - mean_r) / std_r

    anomalies = df[df["residual_zscore"].abs() > threshold].copy()
    return anomalies[["year_month", "load_sum", "residual", "residual_zscore"]].reset_index(drop=True)


FUEL_LABELS = {
    "RA000": "Renewables & biofuels (aggregate)",
    "RA100": "Hydro total",
    "RA200": "Geothermal",
    "RA300": "Wind total",
    "RA400": "Solar total",
    "RA500_5160": "Other renewables",
}


def get_generation_by_fuel(country: str):
    """
    Annual renewable generation by fuel/technology (Eurostat).

    Returns columns: country, year, fuel, generation_gwh
    """
    df = load_eurostat_generation_by_fuel_annual()
    df = df[df["country"] == country].copy()

    if df.empty:
        return pd.DataFrame(columns=["country", "year", "fuel", "generation_gwh"])

    value_cols = [code for code in FUEL_LABELS if code in df.columns]

    df_long = df.melt(
        id_vars=["country", "year"],
        value_vars=value_cols,
        var_name="fuel_code",
        value_name="generation_gwh",
    )

    df_long["fuel"] = df_long["fuel_code"].map(FUEL_LABELS)
    df_long = df_long.dropna(subset=["generation_gwh"])

    return df_long[["country", "year", "fuel", "generation_gwh"]].sort_values(
        ["year", "fuel"]
    )