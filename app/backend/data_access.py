import pandas as pd
from pathlib import Path
 
# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------
 
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
 
DAILY_PATH = DATA_DIR / "daily_load-2.csv"
MONTHLY_PATH = DATA_DIR / "monthly_load.csv"
CLEAN_HOURLY_PATH = DATA_DIR / "clean_energy_load.csv"
FLOW_ENERGY_PATH = DATA_DIR / "energy_flows.csv"
FLOW_TOTAL_PATH = DATA_DIR / "flows_total.csv"
COUNTRY_TOTALS_PATH = DATA_DIR / "country_totals.csv"
EUROSTAT_SHARE_ANNUAL_PATH = DATA_DIR / "renewable_share_eurostat_annual.csv"
EUROSTAT_FUEL_ANNUAL_PATH = DATA_DIR / "eurostat_generation_by_fuel_annual.csv"
 
# --------------------------------------------------------------------
# Cached dataframes
# --------------------------------------------------------------------
 
_daily_df = None
_monthly_df = None
_energy_flows_df = None
_flow_totals_df = None
_country_totals_df = None
_eu_share_annual_df = None
_eu_fuel_annual_df = None
 
 
# --------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------
 
COUNTRY_ISO_MAP = {
    "AL": "ALB", "AT": "AUT", "BA": "BIH", "BE": "BEL", "BG": "BGR",
    "CH": "CHE", "CY": "CYP", "CZ": "CZE", "DE": "DEU", "DK": "DNK",
    "EE": "EST", "ES": "ESP", "FI": "FIN", "FR": "FRA", "GB": "GBR",
    "GE": "GEO", "GR": "GRC", "HR": "HRV", "HU": "HUN", "IE": "IRL",
    "IS": "ISL", "IT": "ITA", "LT": "LTU", "LU": "LUX", "LV": "LVA",
    "MD": "MDA", "ME": "MNE", "MK": "MKD", "MT": "MLT", "NL": "NLD",
    "NO": "NOR", "PL": "POL", "PT": "PRT", "RO": "ROU", "RS": "SRB",
    "SE": "SWE", "SI": "SVN", "SK": "SVK", "TR": "TUR", "UA": "UKR",
    "XK": "XKX",
}
 
COUNTRY_NAMES = {
    "AL": "Albania", "AT": "Austria", "BA": "Bosnia & Herzegovina",
    "BE": "Belgium", "BG": "Bulgaria", "CH": "Switzerland", "CY": "Cyprus",
    "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "ES": "Spain", "FI": "Finland", "FR": "France", "GB": "United Kingdom",
    "GE": "Georgia", "GR": "Greece", "HR": "Croatia", "HU": "Hungary",
    "IE": "Ireland", "IS": "Iceland", "IT": "Italy", "LT": "Lithuania",
    "LU": "Luxembourg", "LV": "Latvia", "MD": "Moldova", "ME": "Montenegro",
    "MK": "North Macedonia", "MT": "Malta", "NL": "Netherlands",
    "NO": "Norway", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "RS": "Serbia", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
    "TR": "Turkey", "UA": "Ukraine", "XK": "Kosovo",
}
 
COUNTRY_NAMES_PL = {
    "AL": "Albania", "AT": "Austria", "BA": "Bośnia i Hercegowina",
    "BE": "Belgia", "BG": "Bułgaria", "CH": "Szwajcaria", "CY": "Cypr",
    "CZ": "Czechy", "DE": "Niemcy", "DK": "Dania", "EE": "Estonia",
    "ES": "Hiszpania", "FI": "Finlandia", "FR": "Francja", "GB": "Wielka Brytania",
    "GE": "Gruzja", "GR": "Grecja", "HR": "Chorwacja", "HU": "Węgry",
    "IE": "Irlandia", "IS": "Islandia", "IT": "Włochy", "LT": "Litwa",
    "LU": "Luksemburg", "LV": "Łotwa", "MD": "Mołdawia", "ME": "Czarnogóra",
    "MK": "Macedonia Północna", "MT": "Malta", "NL": "Holandia",
    "NO": "Norwegia", "PL": "Polska", "PT": "Portugalia", "RO": "Rumunia",
    "RS": "Serbia", "SE": "Szwecja", "SI": "Słowenia", "SK": "Słowacja",
    "TR": "Turcja", "UA": "Ukraina", "XK": "Kosowo",
}
 
FUEL_LABELS = {
    "RA000": "Renewables & biofuels (aggregate)",
    "RA100": "Hydro total",
    "RA200": "Geothermal",
    "RA300": "Wind total",
    "RA400": "Solar total",
    "RA500_5160": "Other renewables",
}
 
 
# --------------------------------------------------------------------
# Data loaders
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
 
def load_energy_flows():
    global _energy_flows_df
    if _energy_flows_df is None:
        _energy_flows_df = pd.read_csv(FLOW_ENERGY_PATH, parse_dates=["date"])
    return _energy_flows_df
 
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
 
def load_eurostat_share_annual():
    global _eu_share_annual_df
    if _eu_share_annual_df is None:
        _eu_share_annual_df = pd.read_csv(EUROSTAT_SHARE_ANNUAL_PATH)
    return _eu_share_annual_df
 
def load_eurostat_generation_by_fuel_annual():
    global _eu_fuel_annual_df
    if _eu_fuel_annual_df is None:
        _eu_fuel_annual_df = pd.read_csv(EUROSTAT_FUEL_ANNUAL_PATH)
    return _eu_fuel_annual_df
 
# --------------------------------------------------------------------
# Coverage filter helper
# --------------------------------------------------------------------
 
def _filter_coverage(df, min_coverage=0.7):
    """Remove months with insufficient daily coverage from monthly load data."""
    df = df.copy()
    df["expected_days"] = df["year_month"].dt.days_in_month
    df["coverage"] = df["days_used"] / df["expected_days"]
    return df[df["coverage"] >= min_coverage].drop(columns=["expected_days", "coverage"])
 
 
# --------------------------------------------------------------------
# Core data access functions
# --------------------------------------------------------------------
 
def get_daily_load(country: str, start_date, end_date):
    df = load_daily()
    mask = (
        (df["country"] == country)
        & (df["date"] >= pd.to_datetime(start_date))
        & (df["date"] <= pd.to_datetime(end_date))
    )
    return df.loc[mask].sort_values("date")
 
def get_monthly_load_clean(country: str, start_month, end_month, min_coverage: float = 0.7):
    """Get monthly load excluding months with insufficient daily coverage."""
    df = load_monthly()
    mask = (
        (df["country"] == country)
        & (df["year_month"] >= pd.to_datetime(start_month))
        & (df["year_month"] <= pd.to_datetime(end_month))
    )
    df = df.loc[mask].sort_values("year_month").copy()
    if df.empty:
        return df
    return _filter_coverage(df, min_coverage)
 
def get_annual_load(country: str):
    """Aggregate monthly load to annual totals. Excludes incomplete months."""
    df = load_monthly()
    df_country = df.loc[df["country"] == country].copy()
    if df_country.empty:
        return pd.DataFrame(columns=["year", "annual_load_mwh"])
    df_country = _filter_coverage(df_country)
    df_country["year"] = df_country["year_month"].dt.year
    annual = (
        df_country.groupby("year", observed=True)["load_sum"]
        .sum().reset_index()
        .rename(columns={"load_sum": "annual_load_mwh"})
        .sort_values("year")
    )
    return annual
 
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
        .sum().reset_index()
        .rename(columns={"flow_signed": "net_flow"})
        .sort_values("date")
    )
    return grouped
 
def get_country_totals():
    return load_country_totals()
 
def get_border_partners(country: str):
    df = load_flow_totals()
    partners = df.loc[df["country"] == country, "partner"].dropna().unique()
    return sorted(partners)
 
 
def get_generation_share(country: str):
    """Annual renewable generation share (Eurostat)."""
    df = load_eurostat_share_annual()
    df = df[df["country"] == country].copy()
    if df.empty:
        return pd.DataFrame(columns=["country", "year", "renewable_generation_gwh", "total_generation_gwh", "renewable_share"])
    return df.sort_values("year").reset_index(drop=True)
 
def get_generation_year_bounds():
    df = load_eurostat_share_annual().copy()
    df = df.dropna(subset=["renewable_generation_gwh", "total_generation_gwh"])
    return int(df["year"].min()), int(df["year"].max())
 
def get_generation_by_fuel(country: str):
    """Annual renewable generation by fuel/technology (Eurostat)."""
    df = load_eurostat_generation_by_fuel_annual()
    df = df[df["country"] == country].copy()
    if df.empty:
        return pd.DataFrame(columns=["country", "year", "fuel", "generation_gwh"])
    value_cols = [code for code in FUEL_LABELS if code in df.columns]
    df_long = df.melt(id_vars=["country", "year"], value_vars=value_cols, var_name="fuel_code", value_name="generation_gwh")
    df_long["fuel"] = df_long["fuel_code"].map(FUEL_LABELS)
    df_long = df_long.dropna(subset=["generation_gwh"])
    return df_long[["country", "year", "fuel", "generation_gwh"]].sort_values(["year", "fuel"])
 
def compute_cagr(start_value, end_value, n_years):
    """Compound Annual Growth Rate (%)."""
    if start_value <= 0 or end_value <= 0 or n_years <= 0:
        return None
    return ((end_value / start_value) ** (1 / n_years) - 1) * 100
 
 
# --------------------------------------------------------------------
# Country overview
# --------------------------------------------------------------------
 
def get_country_overview_kpis(country: str, start_month=None, end_month=None):
    df = load_monthly()
    df_c = df[df["country"] == country].copy()
    if start_month is not None:
        df_c = df_c[df_c["year_month"] >= pd.to_datetime(start_month)]
    if end_month is not None:
        df_c = df_c[df_c["year_month"] <= pd.to_datetime(end_month)]
    if df_c.empty:
        return {}
    df_c = _filter_coverage(df_c)
    if df_c.empty:
        return {}
 
    total_load_mwh = df_c["load_sum"].sum()
    total_load_twh = total_load_mwh / 1_000_000
    avg_monthly_load_gwh = df_c["load_sum"].mean() / 1_000
    peak_demand_mw = df_c["load_peak"].max()
    peak_row = df_c.loc[df_c["load_peak"].idxmax()]
    peak_demand_month = peak_row["year_month"]
    overall_avg = df_c["load_mean"].mean()
    load_factor = overall_avg / peak_demand_mw if peak_demand_mw > 0 else 0
 
    df_c["year"] = df_c["year_month"].dt.year
    yearly_load = df_c.groupby("year")["load_sum"].sum()
    if len(yearly_load) >= 2:
        last_year = yearly_load.iloc[-1]
        prev_year = yearly_load.iloc[-2]
        yoy_load_change_pct = ((last_year - prev_year) / prev_year) * 100
    else:
        yoy_load_change_pct = None
 
    totals = get_country_totals()
    row = totals.loc[totals["country"] == country]
    if not row.empty:
        total_import = row.iloc[0]["total_import"] / 1_000
        total_export = row.iloc[0]["total_export"] / 1_000
        net_position = total_export - total_import
        net_label = "Net exporter" if net_position > 0 else "Net importer"
    else:
        total_import = 0
        total_export = 0
        net_position = 0
        net_label = "N/A"
 
    df_gen = load_eurostat_share_annual()
    df_gen_c = df_gen[(df_gen["country"] == country)].dropna(subset=["renewable_share"])
    if not df_gen_c.empty:
        latest_gen = df_gen_c.sort_values("year").iloc[-1]
        renewable_share_pct = latest_gen["renewable_share"] * 100
        renewable_year = int(latest_gen["year"])
    else:
        renewable_share_pct = None
        renewable_year = None
 
    return {
        "total_load_twh": round(total_load_twh, 2),
        "avg_monthly_load_gwh": round(avg_monthly_load_gwh, 1),
        "peak_demand_mw": round(peak_demand_mw, 0),
        "peak_demand_month": peak_demand_month,
        "load_factor": round(load_factor, 3),
        "yoy_load_change_pct": round(yoy_load_change_pct, 1) if yoy_load_change_pct is not None else None,
        "total_import_gwh": round(total_import, 1),
        "total_export_gwh": round(total_export, 1),
        "net_position_gwh": round(net_position, 1),
        "net_position_label": net_label,
        "renewable_share_pct": round(renewable_share_pct, 1) if renewable_share_pct is not None else None,
        "renewable_year": renewable_year,
    }
 
def get_annual_load_summary(country: str):
    df = load_monthly()
    df_c = df[df["country"] == country].copy()
    if df_c.empty:
        return pd.DataFrame(columns=["year", "annual_load_twh", "peak_mw", "load_factor"])
    df_c = _filter_coverage(df_c)
    df_c["year"] = df_c["year_month"].dt.year
    annual = df_c.groupby("year").agg(
        annual_load_mwh=("load_sum", "sum"),
        peak_mw=("load_peak", "max"),
        avg_mean=("load_mean", "mean"),
    ).reset_index()
    annual["annual_load_twh"] = (annual["annual_load_mwh"] / 1_000_000).round(3)
    annual["load_factor"] = (annual["avg_mean"] / annual["peak_mw"]).round(3)
    return annual[["year", "annual_load_twh", "peak_mw", "load_factor"]].sort_values("year")
 
 
# --------------------------------------------------------------------
# Load patterns
# --------------------------------------------------------------------
 
def get_hourly_load_window(country: str, start_ts, end_ts):
    start_ts = pd.to_datetime(start_ts)
    end_ts = pd.to_datetime(end_ts)
    chunks = []
    read_cols = ["timestamp", "country", "load"]
    dtypes = {"country": "category", "load": "float32"}
    for chunk in pd.read_csv(CLEAN_HOURLY_PATH, usecols=read_cols, dtype=dtypes, parse_dates=["timestamp"], chunksize=500_000):
        mask = (chunk["country"] == country) & (chunk["timestamp"] >= start_ts) & (chunk["timestamp"] <= end_ts)
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
        .agg(["mean", "max"]).reset_index()
        .rename(columns={"mean": "load_mean", "max": "load_peak"})
        .sort_values("hour")
    )
    return profile
 
def get_daily_load_with_daytype(country: str, start_date, end_date):
    df = get_daily_load(country, start_date, end_date)
    if df.empty:
        return df
    df = df.copy()
    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_name"] = df["date"].dt.day_name()
    df["day_type"] = df["day_of_week"].apply(lambda d: "Weekend" if d >= 5 else "Weekday")
    return df
 
def get_weekday_weekend_comparison(country: str, start_date, end_date):
    df = get_daily_load_with_daytype(country, start_date, end_date)
    if df.empty:
        return pd.DataFrame(columns=["day_type", "avg_load_sum", "avg_load_peak", "avg_load_mean", "count"])
    summary = df.groupby("day_type").agg(
        avg_load_sum=("load_sum", "mean"), avg_load_peak=("load_peak", "mean"),
        avg_load_mean=("load_mean", "mean"), count=("date", "count"),
    ).reset_index()
    return summary
 
def get_day_of_week_profile(country: str, start_date, end_date):
    df = get_daily_load_with_daytype(country, start_date, end_date)
    if df.empty:
        return pd.DataFrame(columns=["day_of_week", "day_name", "avg_load_sum", "avg_load_peak", "std_load_sum"])
    profile = df.groupby(["day_of_week", "day_name"]).agg(
        avg_load_sum=("load_sum", "mean"), avg_load_peak=("load_peak", "mean"), std_load_sum=("load_sum", "std"),
    ).reset_index().sort_values("day_of_week")
    return profile
 
 
def get_load_statistics(country: str, start_date, end_date):
    df = get_daily_load_with_daytype(country, start_date, end_date)
    if df.empty:
        return {}
    total_days = len(df)
    total_load_gwh = df["load_sum"].sum() / 1_000
    avg_daily = df["load_sum"].mean()
    peak_load = df["load_peak"].max()
    peak_row = df.loc[df["load_peak"].idxmax()]
    peak_date = peak_row["date"]
    min_load = df["load_peak"].min()
    min_row = df.loc[df["load_peak"].idxmin()]
    min_date = min_row["date"]
    overall_mean = df["load_mean"].mean()
    load_factor = overall_mean / peak_load if peak_load > 0 else 0
    std_daily = df["load_sum"].std()
    coeff_variation = std_daily / avg_daily if avg_daily > 0 else 0
    weekday_avg = df[df["day_type"] == "Weekday"]["load_sum"].mean()
    weekend_avg = df[df["day_type"] == "Weekend"]["load_sum"].mean()
    weekend_drop_pct = ((weekday_avg - weekend_avg) / weekday_avg) * 100 if weekday_avg > 0 else 0
    return {
        "total_days": total_days, "total_load_gwh": round(total_load_gwh, 1),
        "avg_daily_load_mwh": round(avg_daily, 0), "peak_load_mw": round(peak_load, 0),
        "peak_date": peak_date, "min_load_mw": round(min_load, 0), "min_date": min_date,
        "load_factor": round(load_factor, 3), "std_daily_mwh": round(std_daily, 0),
        "coeff_variation": round(coeff_variation, 3),
        "weekday_avg_mwh": round(weekday_avg, 0) if not pd.isna(weekday_avg) else 0,
        "weekend_avg_mwh": round(weekend_avg, 0) if not pd.isna(weekend_avg) else 0,
        "weekend_drop_pct": round(weekend_drop_pct, 1),
    }
 
def get_monthly_load_heatmap_data(country: str, start_date, end_date):
    df = get_daily_load(country, start_date, end_date)
    if df.empty:
        return pd.DataFrame(columns=["year", "month", "avg_daily_load"])
    df = df.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    heatmap = df.groupby(["year", "month"])["load_sum"].mean().reset_index().rename(columns={"load_sum": "avg_daily_load"})
    return heatmap
 
 
# --------------------------------------------------------------------
# Seasonality decomposition
# --------------------------------------------------------------------
 
def get_seasonal_decomposition(country: str, start_month=None, end_month=None):
    from statsmodels.tsa.seasonal import STL
    df = load_monthly()
    df_c = df.loc[df["country"] == country].copy().sort_values("year_month")
    if start_month is not None:
        df_c = df_c[df_c["year_month"] >= pd.to_datetime(start_month)]
    if end_month is not None:
        df_c = df_c[df_c["year_month"] <= pd.to_datetime(end_month)]
    df_c = _filter_coverage(df_c)
    if len(df_c) < 24:
        return pd.DataFrame(columns=["year_month", "load_sum", "trend", "seasonal", "residual"])
    series = df_c.set_index("year_month")["load_sum"]
    series.index = pd.DatetimeIndex(series.index, freq="MS")
    stl = STL(series, period=12, robust=True)
    result = stl.fit()
    out = pd.DataFrame({
        "year_month": series.index, "load_sum": series.values,
        "trend": result.trend, "seasonal": result.seasonal, "residual": result.resid,
    })
    return out.reset_index(drop=True)
 
def get_seasonal_strength(country: str, start_month=None, end_month=None):
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
 
 
# --------------------------------------------------------------------
# Interconnectors
# --------------------------------------------------------------------
 
def get_border_flow_directional(country: str, partner: str, start_date, end_date):
    df = load_energy_flows()
    mask = (df["country"] == country) & (df["partner"] == partner) & (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
    df_border = df.loc[mask].copy()
    if df_border.empty:
        return pd.DataFrame(columns=["date", "import_gwh", "export_gwh", "net_gwh"])
    pivot = df_border.groupby(["date", "Direction"])["flow"].sum().reset_index().pivot_table(index="date", columns="Direction", values="flow", fill_value=0).reset_index()
    if "Import" not in pivot.columns:
        pivot["Import"] = 0
    if "Export" not in pivot.columns:
        pivot["Export"] = 0
    pivot = pivot.rename(columns={"Import": "import_gwh", "Export": "export_gwh"})
    pivot["import_gwh"] = pivot["import_gwh"] / 1000
    pivot["export_gwh"] = pivot["export_gwh"] / 1000
    pivot["net_gwh"] = pivot["import_gwh"] - pivot["export_gwh"]
    return pivot[["date", "import_gwh", "export_gwh", "net_gwh"]].sort_values("date").reset_index(drop=True)
 
def get_top_partners_directional(country: str):
    df = load_energy_flows()
    df_c = df[df["country"] == country].copy()
    if df_c.empty:
        return pd.DataFrame(columns=["partner", "total_import_gwh", "total_export_gwh", "net_gwh", "total_flow_gwh", "balance_label"])
    imports = df_c[df_c["Direction"] == "Import"].groupby("partner")["flow"].sum().reset_index().rename(columns={"flow": "total_import_gwh"})
    exports = df_c[df_c["Direction"] == "Export"].groupby("partner")["flow"].sum().reset_index().rename(columns={"flow": "total_export_gwh"})
    merged = imports.merge(exports, on="partner", how="outer").fillna(0)
    merged["total_import_gwh"] = merged["total_import_gwh"] / 1000
    merged["total_export_gwh"] = merged["total_export_gwh"] / 1000
    merged["net_gwh"] = merged["total_import_gwh"] - merged["total_export_gwh"]
    merged["total_flow_gwh"] = merged["total_import_gwh"] + merged["total_export_gwh"]
    merged["balance_label"] = merged["net_gwh"].apply(lambda v: "Net importer" if v > 0 else "Net exporter")
    return merged.sort_values("total_flow_gwh", ascending=False).reset_index(drop=True)
 
def get_interconnector_stats(country: str, partner: str, start_date, end_date):
    df = get_border_flow_directional(country, partner, start_date, end_date)
    if df.empty:
        return {}
    total_import = df["import_gwh"].sum()
    total_export = df["export_gwh"].sum()
    net = total_import - total_export
    balance = "Net importer" if net > 0 else "Net exporter"
    peak_import_idx = df["import_gwh"].idxmax()
    peak_export_idx = df["export_gwh"].idxmax()
    months_importer = (df["net_gwh"] > 0).sum()
    months_exporter = (df["net_gwh"] <= 0).sum()
    return {
        "total_import_gwh": round(total_import, 1), "total_export_gwh": round(total_export, 1),
        "net_gwh": round(net, 1), "balance_label": balance,
        "peak_import_month": df.loc[peak_import_idx, "date"], "peak_import_gwh": round(df.loc[peak_import_idx, "import_gwh"], 1),
        "peak_export_month": df.loc[peak_export_idx, "date"], "peak_export_gwh": round(df.loc[peak_export_idx, "export_gwh"], 1),
        "months_net_importer": int(months_importer), "months_net_exporter": int(months_exporter),
    }
 
 
# --------------------------------------------------------------------
# Compare countries
# --------------------------------------------------------------------
 
def get_indexed_load(countries: list, start_month, end_month, base_month=None):
    df = load_monthly()
    mask = (df["country"].isin(countries)) & (df["year_month"] >= pd.to_datetime(start_month)) & (df["year_month"] <= pd.to_datetime(end_month))
    df_filtered = df.loc[mask].copy()
    if df_filtered.empty:
        return pd.DataFrame(columns=["year_month", "country", "load_sum", "indexed_load"])
    df_filtered = _filter_coverage(df_filtered)
    if base_month is not None:
        base_df = df_filtered[df_filtered["year_month"] == pd.to_datetime(base_month)]
    else:
        base_df = df_filtered.sort_values("year_month").groupby("country").first().reset_index()
    base_values = base_df.set_index("country")["load_sum"].to_dict()
    df_filtered["base_load"] = df_filtered["country"].map(base_values)
    df_filtered["indexed_load"] = (df_filtered["load_sum"] / df_filtered["base_load"]) * 100
    return df_filtered[["year_month", "country", "load_sum", "indexed_load"]].sort_values(["country", "year_month"]).reset_index(drop=True)
 
def get_country_comparison_stats(countries: list, start_month, end_month):
    df = load_monthly()
    mask = (df["country"].isin(countries)) & (df["year_month"] >= pd.to_datetime(start_month)) & (df["year_month"] <= pd.to_datetime(end_month))
    df_filtered = df.loc[mask].copy()
    if df_filtered.empty:
        return pd.DataFrame()
    df_filtered = _filter_coverage(df_filtered)
    rows = []
    for country in countries:
        df_c = df_filtered[df_filtered["country"] == country]
        if df_c.empty:
            continue
        total_load_twh = df_c["load_sum"].sum() / 1_000_000
        avg_monthly_gwh = df_c["load_sum"].mean() / 1_000
        peak_mw = df_c["load_peak"].max()
        df_c = df_c.copy()
        df_c["year"] = df_c["year_month"].dt.year
        yearly = df_c.groupby("year")["load_sum"].sum()
        growth = ((yearly.iloc[-1] - yearly.iloc[0]) / yearly.iloc[0]) * 100 if len(yearly) >= 2 else 0
        cv = df_c["load_sum"].std() / df_c["load_sum"].mean() if df_c["load_sum"].mean() > 0 else 0
        df_gen = load_eurostat_share_annual()
        df_gen_c = df_gen[df_gen["country"] == country].dropna(subset=["renewable_share"])
        ren_share = (df_gen_c.sort_values("year").iloc[-1]["renewable_share"] * 100) if not df_gen_c.empty else None
        totals = get_country_totals()
        row_t = totals[totals["country"] == country]
        net_label = "Net exporter" if (not row_t.empty and row_t.iloc[0]["total_export"] - row_t.iloc[0]["total_import"] > 0) else "Net importer" if not row_t.empty else "N/A"
        rows.append({"country": country, "total_load_twh": round(total_load_twh, 2), "avg_monthly_gwh": round(avg_monthly_gwh, 1), "peak_mw": round(peak_mw, 0), "load_growth_pct": round(growth, 1), "volatility_cv": round(cv, 3), "renewable_share_pct": round(ren_share, 1) if ren_share is not None else None, "net_position": net_label})
    return pd.DataFrame(rows) if rows else pd.DataFrame()
 
def get_yoy_load_comparison(countries: list, start_month, end_month):
    df = load_monthly()
    mask = (df["country"].isin(countries)) & (df["year_month"] >= pd.to_datetime(start_month)) & (df["year_month"] <= pd.to_datetime(end_month))
    df_filtered = df.loc[mask].copy()
    df_filtered = _filter_coverage(df_filtered)
    df_filtered["year"] = df_filtered["year_month"].dt.year
    annual = df_filtered.groupby(["country", "year"])["load_sum"].sum().reset_index().rename(columns={"load_sum": "annual_load_mwh"})
    frames = []
    for country in countries:
        df_c = annual[annual["country"] == country].sort_values("year").copy()
        df_c["prev_load"] = df_c["annual_load_mwh"].shift(1)
        df_c["yoy_pct"] = ((df_c["annual_load_mwh"] - df_c["prev_load"]) / df_c["prev_load"]) * 100
        frames.append(df_c)
    if not frames:
        return pd.DataFrame(columns=["year", "country", "annual_load_mwh", "yoy_pct"])
    result = pd.concat(frames, ignore_index=True)
    return result[["year", "country", "annual_load_mwh", "yoy_pct"]].dropna(subset=["yoy_pct"])
 
 
# --------------------------------------------------------------------
# Renewables vs load
# --------------------------------------------------------------------
 
def get_renewables_vs_load_detail(country: str, start_year=None, end_year=None):
    df_gen = get_generation_share(country)
    df_load = get_annual_load(country)
    if df_gen.empty or df_load.empty:
        return pd.DataFrame()
    df = df_gen.merge(df_load, on="year", how="inner")
    df = df.dropna(subset=["total_generation_gwh", "renewable_generation_gwh"])
    if start_year is not None:
        df = df[df["year"] >= start_year]
    if end_year is not None:
        df = df[df["year"] <= end_year]
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["annual_load_gwh"] = df["annual_load_mwh"] / 1000.0
    df["non_renewable_gwh"] = df["total_generation_gwh"] - df["renewable_generation_gwh"]
    df["generation_surplus_gwh"] = df["total_generation_gwh"] - df["annual_load_gwh"]
    df["surplus_ratio"] = df["generation_surplus_gwh"] / df["annual_load_gwh"]
    df["renewable_coverage_pct"] = (df["renewable_generation_gwh"] / df["annual_load_gwh"]) * 100
    df["fossil_dependency_pct"] = (df["non_renewable_gwh"] / df["annual_load_gwh"]) * 100
    return df.sort_values("year").reset_index(drop=True)
 
def get_renewables_load_kpis(country: str, start_year=None, end_year=None):
    df = get_renewables_vs_load_detail(country, start_year, end_year)
    if df.empty:
        return {}
    latest = df.iloc[-1]
    earliest = df.iloc[0]
    coverage_start = earliest["renewable_coverage_pct"]
    coverage_end = latest["renewable_coverage_pct"]
    coverage_change = coverage_end - coverage_start
    load_start = earliest["annual_load_gwh"]
    load_end = latest["annual_load_gwh"]
    load_change_pct = ((load_end - load_start) / load_start) * 100 if load_start > 0 else 0
    ren_start = earliest["renewable_generation_gwh"]
    ren_end = latest["renewable_generation_gwh"]
    ren_change_pct = ((ren_end - ren_start) / ren_start) * 100 if ren_start > 0 else 0
    fossil_start = earliest["fossil_dependency_pct"]
    fossil_end = latest["fossil_dependency_pct"]
    fossil_displacement = fossil_start - fossil_end
    return {
        "latest_year": int(latest["year"]), "renewable_coverage_pct": round(coverage_end, 1),
        "coverage_change_pp": round(coverage_change, 1), "load_change_pct": round(load_change_pct, 1),
        "renewable_change_pct": round(ren_change_pct, 1), "fossil_displacement_pp": round(fossil_displacement, 1),
        "latest_surplus_gwh": round(latest["generation_surplus_gwh"], 1),
        "latest_load_gwh": round(load_end, 1), "latest_renewable_gwh": round(ren_end, 1),
        "latest_total_gen_gwh": round(latest["total_generation_gwh"], 1),
    }
 
 
# --------------------------------------------------------------------
# Compare renewables
# --------------------------------------------------------------------
 
def get_renewable_share_comparison(countries: list, start_year: int, end_year: int):
    frames = []
    for country in countries:
        df_c = get_generation_share(country)
        if df_c.empty:
            continue
        df_c = df_c[(df_c["year"] >= start_year) & (df_c["year"] <= end_year)].copy()
        df_c = df_c.dropna(subset=["renewable_share"])
        df_c["country"] = country
        frames.append(df_c)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
 
def get_technology_mix_comparison(countries: list, year: int):
    fuel_codes = {"RA100": "Hydro", "RA300": "Wind", "RA400": "Solar", "RA200": "Geothermal", "RA500_5160": "Other renewables"}
    df = load_eurostat_generation_by_fuel_annual()
    df = df[(df["country"].isin(countries)) & (df["year"] == year)]
    rows = []
    for _, row in df.iterrows():
        country = row["country"]
        total_renewable = row.get("RA000", 0)
        if pd.isna(total_renewable) or total_renewable == 0:
            continue
        for code, label in fuel_codes.items():
            val = row.get(code, 0)
            if pd.isna(val):
                val = 0
            share = (val / total_renewable) * 100 if total_renewable > 0 else 0
            rows.append({"country": country, "fuel": label, "generation_gwh": round(val, 1), "share_of_renewable": round(share, 1)})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["country", "fuel", "generation_gwh", "share_of_renewable"])
 
def get_renewable_growth_comparison(countries: list, start_year: int, end_year: int):
    rows = []
    for country in countries:
        df = get_generation_share(country)
        if df.empty:
            continue
        df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()
        df = df.dropna(subset=["renewable_generation_gwh", "renewable_share"])
        if len(df) < 2:
            continue
        first = df.iloc[0]
        last = df.iloc[-1]
        n_years = last["year"] - first["year"]
        if n_years == 0:
            continue
        start_gwh = first["renewable_generation_gwh"]
        end_gwh = last["renewable_generation_gwh"]
        absolute_growth = end_gwh - start_gwh
        growth_pct = ((end_gwh - start_gwh) / start_gwh) * 100 if start_gwh > 0 else 0
        cagr = compute_cagr(start_gwh, end_gwh, n_years)
        rows.append({"country": country, "start_gwh": round(start_gwh, 1), "end_gwh": round(end_gwh, 1), "absolute_growth_gwh": round(absolute_growth, 1), "growth_pct": round(growth_pct, 1), "cagr_pct": round(cagr, 1) if cagr is not None else None, "share_start_pct": round(first["renewable_share"] * 100, 1), "share_end_pct": round(last["renewable_share"] * 100, 1), "share_gain_pp": round((last["renewable_share"] - first["renewable_share"]) * 100, 1)})
    return pd.DataFrame(rows) if rows else pd.DataFrame()
 
def get_renewable_gap_to_target(countries: list, year: int, target_pct: float = 50.0):
    rows = []
    for country in countries:
        df = get_generation_share(country)
        if df.empty:
            continue
        df = df[df["year"] == year].dropna(subset=["renewable_share", "total_generation_gwh"])
        if df.empty:
            continue
        row = df.iloc[0]
        current_share = row["renewable_share"] * 100
        total_gen = row["total_generation_gwh"]
        current_renewable = row["renewable_generation_gwh"]
        gap = target_pct - current_share
        additional_gwh = (target_pct / 100 * total_gen) - current_renewable if gap > 0 else 0
        status = "Above target" if gap <= 0 else ("Close" if gap <= 10 else "Behind")
        rows.append({"country": country, "current_share_pct": round(current_share, 1), "target_pct": target_pct, "gap_pp": round(gap, 1), "additional_gwh_needed": round(additional_gwh, 1), "status": status})
    return pd.DataFrame(rows) if rows else pd.DataFrame()
 
 
# --------------------------------------------------------------------
# Energy transition pace
# --------------------------------------------------------------------
 
def compute_yoy_growth(country: str, start_year=None, end_year=None):
    df = get_generation_share(country)
    if df.empty:
        return pd.DataFrame(columns=["year", "renewable_generation_gwh", "total_generation_gwh", "renewable_share", "yoy_growth_pct"])
    df = df.dropna(subset=["renewable_generation_gwh"]).copy()
    if start_year is not None:
        df = df[df["year"] >= start_year]
    if end_year is not None:
        df = df[df["year"] <= end_year]
    df = df.sort_values("year").reset_index(drop=True)
    df["prev_gen"] = df["renewable_generation_gwh"].shift(1)
    df["yoy_growth_pct"] = ((df["renewable_generation_gwh"] - df["prev_gen"]) / df["prev_gen"]) * 100
    return df.drop(columns=["prev_gen"])
 
def get_transition_scorecard(countries: list, start_year: int, end_year: int):
    rows = []
    for country in countries:
        df = get_generation_share(country)
        if df.empty:
            continue
        df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()
        df = df.dropna(subset=["renewable_share", "renewable_generation_gwh"])
        if len(df) < 2:
            continue
        first = df.iloc[0]
        last = df.iloc[-1]
        n_years = last["year"] - first["year"]
        if n_years == 0:
            continue
        start_share = first["renewable_share"]
        end_share = last["renewable_share"]
        share_change_pp = (end_share - start_share) * 100
        cagr = compute_cagr(first["renewable_generation_gwh"], last["renewable_generation_gwh"], n_years)
        df_yoy = compute_yoy_growth(country, start_year, end_year)
        avg_yoy = df_yoy["yoy_growth_pct"].mean()
        rows.append({"country": country, "start_year": int(first["year"]), "end_year": int(last["year"]), "start_share_pct": round(start_share * 100, 1), "end_share_pct": round(end_share * 100, 1), "share_change_pp": round(share_change_pp, 1), "cagr_pct": round(cagr, 1) if cagr is not None else None, "avg_yoy_growth_pct": round(avg_yoy, 1) if not pd.isna(avg_yoy) else None})
    if not rows:
        return pd.DataFrame()
    scorecard = pd.DataFrame(rows)
    scorecard = scorecard.sort_values("share_change_pp", ascending=False).reset_index(drop=True)
    scorecard["rank"] = scorecard.index + 1
    return scorecard
 
def get_tech_growth(countries: list, start_year: int, end_year: int):
    tech_cols = {"RA100": "Hydro", "RA300": "Wind", "RA400": "Solar", "RA200": "Geothermal", "RA500_5160": "Other renewables"}
    df = load_eurostat_generation_by_fuel_annual()
    df = df[df["country"].isin(countries)]
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    rows = []
    for country in countries:
        df_c = df[df["country"] == country].sort_values("year")
        if len(df_c) < 2:
            continue
        first_row = df_c.iloc[0]
        last_row = df_c.iloc[-1]
        n_years = last_row["year"] - first_row["year"]
        if n_years == 0:
            continue
        for code, label in tech_cols.items():
            if code not in df_c.columns:
                continue
            start_val = first_row.get(code)
            end_val = last_row.get(code)
            if pd.isna(start_val) or pd.isna(end_val):
                continue
            cagr = compute_cagr(start_val, end_val, n_years)
            rows.append({"country": country, "technology": label, "start_gwh": round(start_val, 1), "end_gwh": round(end_val, 1), "cagr_pct": round(cagr, 1) if cagr is not None else None})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["country", "technology", "start_gwh", "end_gwh", "cagr_pct"])
 
def get_transition_acceleration(countries: list, start_year: int, end_year: int):
    rows = []
    for country in countries:
        df_yoy = compute_yoy_growth(country, start_year, end_year)
        df_yoy = df_yoy.dropna(subset=["yoy_growth_pct"])
        if len(df_yoy) < 4:
            continue
        mid_idx = len(df_yoy) // 2
        first_half_avg = df_yoy.iloc[:mid_idx]["yoy_growth_pct"].mean()
        second_half_avg = df_yoy.iloc[mid_idx:]["yoy_growth_pct"].mean()
        rows.append({"country": country, "first_half_avg_yoy": round(first_half_avg, 1), "second_half_avg_yoy": round(second_half_avg, 1), "acceleration": round(second_half_avg - first_half_avg, 1)})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["country", "first_half_avg_yoy", "second_half_avg_yoy", "acceleration"])
 
 
# --------------------------------------------------------------------
# Self-sufficiency & import dependency
# --------------------------------------------------------------------
 
def get_annual_net_flows(country: str):
    df = load_energy_flows()
    df_c = df[df["country"] == country].copy()
    if df_c.empty:
        return pd.DataFrame(columns=["year", "annual_import", "annual_export", "net_import"])
    df_c["year"] = df_c["date"].dt.year
    imports = df_c[df_c["Direction"] == "Import"].groupby("year", observed=True)["flow"].sum().reset_index().rename(columns={"flow": "annual_import"})
    exports = df_c[df_c["Direction"] == "Export"].groupby("year", observed=True)["flow"].sum().reset_index().rename(columns={"flow": "annual_export"})
    merged = imports.merge(exports, on="year", how="outer").fillna(0)
    merged["net_import"] = merged["annual_import"] - merged["annual_export"]
    return merged.sort_values("year").reset_index(drop=True)
 
def get_self_sufficiency(country: str):
    df_gen = get_generation_share(country)
    df_load = get_annual_load(country)
    df_flows = get_annual_net_flows(country)
    if df_gen.empty or df_load.empty:
        return pd.DataFrame()
    df = df_gen.merge(df_load, on="year", how="inner")
    df["annual_load_gwh"] = df["annual_load_mwh"] / 1000.0
    if not df_flows.empty:
        df_flows["annual_import_gwh"] = df_flows["annual_import"] / 1000.0
        df_flows["annual_export_gwh"] = df_flows["annual_export"] / 1000.0
        df_flows["net_import_gwh"] = df_flows["net_import"] / 1000.0
        df = df.merge(df_flows[["year", "annual_import_gwh", "annual_export_gwh", "net_import_gwh"]], on="year", how="left")
    else:
        df["annual_import_gwh"] = 0.0
        df["annual_export_gwh"] = 0.0
        df["net_import_gwh"] = 0.0
    df = df.fillna({"annual_import_gwh": 0, "annual_export_gwh": 0, "net_import_gwh": 0})
    df["self_sufficiency_ratio"] = df["total_generation_gwh"] / df["annual_load_gwh"]
    df["import_dependency"] = df["net_import_gwh"].clip(lower=0) / df["annual_load_gwh"]
    df["renewable_self_sufficiency"] = df["renewable_generation_gwh"] / df["annual_load_gwh"]
    df["export_surplus"] = ((df["total_generation_gwh"] - df["annual_load_gwh"]) / df["total_generation_gwh"]).clip(lower=0)
    return df.sort_values("year").reset_index(drop=True)
 
def get_self_sufficiency_comparison(countries: list, start_year: int, end_year: int):
    rows = []
    for country in countries:
        df = get_self_sufficiency(country)
        if df.empty:
            continue
        df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
        if df.empty:
            continue
        latest = df.iloc[-1]
        rows.append({"country": country, "year": int(latest["year"]), "self_sufficiency_ratio": round(latest["self_sufficiency_ratio"], 3), "import_dependency": round(latest["import_dependency"], 3), "renewable_self_sufficiency": round(latest["renewable_self_sufficiency"], 3), "export_surplus": round(latest["export_surplus"], 3)})
    return pd.DataFrame(rows) if rows else pd.DataFrame()
 
 
# --------------------------------------------------------------------
# Map visualization
# --------------------------------------------------------------------
 
def get_map_renewable_share(year: int):
    df = load_eurostat_share_annual()
    df = df[df["year"] == year].copy()
    df = df.dropna(subset=["renewable_share"])
    df["iso_alpha3"] = df["country"].map(COUNTRY_ISO_MAP)
    df["country_name"] = df["country"].map(COUNTRY_NAMES)
    df["renewable_share_pct"] = (df["renewable_share"] * 100).round(1)
    return df[["country", "iso_alpha3", "country_name", "year", "renewable_share_pct"]].reset_index(drop=True)
 
def get_map_load_intensity(year: int):
    df = load_monthly()
    df = _filter_coverage(df)
    df["year"] = df["year_month"].dt.year
    df_year = df[df["year"] == year]
    annual = df_year.groupby("country", observed=True)["load_sum"].sum().reset_index().rename(columns={"load_sum": "annual_load_mwh"})
    annual["annual_load_twh"] = (annual["annual_load_mwh"] / 1_000_000).round(2)
    annual["iso_alpha3"] = annual["country"].map(COUNTRY_ISO_MAP)
    annual["country_name"] = annual["country"].map(COUNTRY_NAMES)
    annual["year"] = year
    return annual[["country", "iso_alpha3", "country_name", "year", "annual_load_twh"]].reset_index(drop=True)
 
def get_map_net_flows(year: int):
    df = load_energy_flows()
    df["year"] = df["date"].dt.year
    df_year = df[df["year"] == year]
    if df_year.empty:
        return pd.DataFrame(columns=["country", "iso_alpha3", "country_name", "year", "net_import_gwh", "position"])
    imports = df_year[df_year["Direction"] == "Import"].groupby("country", observed=True)["flow"].sum().reset_index().rename(columns={"flow": "total_import"})
    exports = df_year[df_year["Direction"] == "Export"].groupby("country", observed=True)["flow"].sum().reset_index().rename(columns={"flow": "total_export"})
    merged = imports.merge(exports, on="country", how="outer").fillna(0)
    merged["net_import_gwh"] = ((merged["total_import"] - merged["total_export"]) / 1000).round(1)
    merged["position"] = merged["net_import_gwh"].apply(lambda x: "Net importer" if x > 0 else "Net exporter")
    merged["iso_alpha3"] = merged["country"].map(COUNTRY_ISO_MAP)
    merged["country_name"] = merged["country"].map(COUNTRY_NAMES)
    merged["year"] = year
    return merged[["country", "iso_alpha3", "country_name", "year", "net_import_gwh", "position"]].reset_index(drop=True)
 
def get_map_self_sufficiency(year: int):
    df_gen = load_eurostat_share_annual()
    df_gen = df_gen[df_gen["year"] == year].copy()
    df_gen = df_gen.dropna(subset=["total_generation_gwh"])
    df_load = load_monthly()
    df_load = _filter_coverage(df_load)
    df_load["year"] = df_load["year_month"].dt.year
    df_load_year = df_load[df_load["year"] == year].groupby("country", observed=True)["load_sum"].sum().reset_index().rename(columns={"load_sum": "annual_load_mwh"})
    df_load_year["annual_load_gwh"] = df_load_year["annual_load_mwh"] / 1000
    merged = df_gen.merge(df_load_year[["country", "annual_load_gwh"]], on="country", how="inner")
    merged["self_sufficiency_ratio"] = (merged["total_generation_gwh"] / merged["annual_load_gwh"]).round(3)
    merged["renewable_self_sufficiency_pct"] = ((merged["renewable_generation_gwh"] / merged["annual_load_gwh"]) * 100).round(1)
    merged["iso_alpha3"] = merged["country"].map(COUNTRY_ISO_MAP)
    merged["country_name"] = merged["country"].map(COUNTRY_NAMES)
    return merged[["country", "iso_alpha3", "country_name", "year", "self_sufficiency_ratio", "renewable_self_sufficiency_pct"]].reset_index(drop=True)
 
def get_map_year_bounds():
    df_load = load_monthly()
    load_years = df_load["year_month"].dt.year.unique()
    df_gen = load_eurostat_share_annual()
    df_gen_valid = df_gen.dropna(subset=["total_generation_gwh"])
    gen_years = df_gen_valid["year"].unique()
    common_years = sorted(set(load_years) & set(gen_years))
    if not common_years:
        all_gen_years = df_gen["year"].dropna().unique()
        if len(all_gen_years) > 0:
            return int(min(all_gen_years)), int(max(all_gen_years))
        return 2015, 2024
    return int(min(common_years)), int(max(common_years))
 
# --------------------------------------------------------------------
# Clustering & correlation analysis
# --------------------------------------------------------------------
 
def get_clustering_features(year: int):
    df = load_eurostat_generation_by_fuel_annual()
    df_year = df[df["year"] == year].copy()
    feature_cols = ["share_ra100", "share_ra300", "share_ra400", "share_ra000", "share_c0000", "share_g3000", "share_n9000"]
    available_cols = [c for c in feature_cols if c in df_year.columns]
    df_year = df_year[["country"] + available_cols].copy()
    df_year = df_year.dropna(subset=available_cols, how="all")
    df_year[available_cols] = df_year[available_cols].fillna(0)
    df_year["country_name"] = df_year["country"].map(COUNTRY_NAMES)
    return df_year.reset_index(drop=True)
 
def get_clustering_results(year: int, n_clusters: int = 4):
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    df = get_clustering_features(year)
    if df.empty or len(df) < n_clusters:
        return pd.DataFrame(), pd.DataFrame()
    feature_cols = [c for c in df.columns if c.startswith("share_")]
    scaler = StandardScaler()
    X = scaler.fit_transform(df[feature_cols].values)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster"] = kmeans.fit_predict(X)
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)
    df["pca_x"] = coords[:, 0]
    df["pca_y"] = coords[:, 1]
    df["pca_var_x"] = round(pca.explained_variance_ratio_[0] * 100, 1)
    df["pca_var_y"] = round(pca.explained_variance_ratio_[1] * 100, 1)
    centers_original = scaler.inverse_transform(kmeans.cluster_centers_)
    df_centers = pd.DataFrame(centers_original, columns=feature_cols)
    df_centers["cluster"] = range(n_clusters)
    return df, df_centers
 
_corr_cache = {}
 
def get_load_correlation_matrix(start_year: int, end_year: int):
    cache_key = (start_year, end_year)
    if cache_key in _corr_cache:
        return _corr_cache[cache_key]
    df = load_monthly()
    df = _filter_coverage(df)
    df["year"] = df["year_month"].dt.year
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    pivot = df.pivot_table(index="year_month", columns="country", values="load_sum", aggfunc="sum")
    threshold = len(pivot) * 0.7
    pivot = pivot.dropna(axis=1, thresh=int(threshold))
    pivot = pivot.ffill().bfill()
    corr_matrix = pivot.corr()
    countries_used = list(corr_matrix.columns)
    _corr_cache[cache_key] = (corr_matrix, countries_used)
    return corr_matrix, countries_used
 
_trajectory_cache = {}
 
def get_transition_trajectory_clusters(n_clusters: int = 4):
    if n_clusters in _trajectory_cache:
        return _trajectory_cache[n_clusters]
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    df = load_eurostat_share_annual()
    df = df.dropna(subset=["renewable_share"])
    pivot = df.pivot_table(index="country", columns="year", values="renewable_share")
    pivot = pivot.dropna(thresh=4)
    pivot = pivot.interpolate(axis=1).bfill(axis=1).ffill(axis=1)
    if len(pivot) < n_clusters:
        return pd.DataFrame(), pd.DataFrame()
    scaler = StandardScaler()
    X = scaler.fit_transform(pivot.values)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    pivot["cluster"] = labels
    pivot["country_name"] = pivot.index.map(COUNTRY_NAMES)
    year_cols = [c for c in pivot.columns if isinstance(c, (int, float))]
    df_summary = pd.DataFrame({"country": pivot.index, "country_name": pivot["country_name"], "cluster": pivot["cluster"]})
    if year_cols:
        df_summary["start_share"] = pivot[year_cols].apply(lambda row: row.dropna().iloc[0] if not row.dropna().empty else None, axis=1).values
        df_summary["end_share"] = pivot[year_cols].apply(lambda row: row.dropna().iloc[-1] if not row.dropna().empty else None, axis=1).values
        df_summary["share_change_pp"] = ((df_summary["end_share"] - df_summary["start_share"]) * 100).round(1)
    df_summary = df_summary.reset_index(drop=True)
    trajectory_frames = []
    for country in pivot.index:
        row = pivot.loc[country]
        cluster = row["cluster"]
        for year in year_cols:
            val = row[year]
            if pd.notna(val):
                trajectory_frames.append({"country": country, "year": int(year), "renewable_share": val, "cluster": int(cluster)})
    df_trajectories = pd.DataFrame(trajectory_frames) if trajectory_frames else pd.DataFrame()
    _trajectory_cache[n_clusters] = (df_trajectories, df_summary)
    return df_trajectories, df_summary