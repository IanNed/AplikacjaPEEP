import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from app.backend.data_access import (
    load_monthly,
    get_monthly_load,
    get_net_country_flows,
    get_indexed_load,
    get_country_comparison_stats,
    get_yoy_load_comparison,
)

dash.register_page(
    __name__,
    path="/compare-countries",
    name="Compare countries",
    title="Compare countries",
)

# Preload monthly data to get countries and date range
_monthly_df = load_monthly()
COUNTRIES = sorted(_monthly_df["country"].unique())
COUNTRY_OPTIONS = [{"label": c, "value": c} for c in COUNTRIES]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()

layout = html.Div(
    [
        html.H2("Compare Countries"),
        html.P(
            "Multi-country comparison with absolute and normalized views. "
            "Indexed load (base=100) allows fair comparison between countries of different sizes.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Countries (select 2-6)"),
                        dcc.Dropdown(
                            id="cc-countries",
                            options=COUNTRY_OPTIONS,
                            value=["DE", "FR", "PL", "ES", "IT"],
                            multi=True,
                            clearable=False,
                        ),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Date range"),
                        dcc.DatePickerRange(
                            id="cc-date-range",
                            min_date_allowed=MIN_DATE,
                            max_date_allowed=MAX_DATE,
                            start_date=MIN_DATE,
                            end_date=MAX_DATE,
                            display_format="YYYY-MM",
                        ),
                    ],
                    style={"width": "45%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        # Section 1: Summary comparison table
        html.H3("Summary Comparison"),
        dash_table.DataTable(
            id="cc-summary-table",
            columns=[],
            data=[],
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "8px"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f0f0f0"},
            style_data_conditional=[
                {
                    "if": {"filter_query": "{load_growth_pct} > 5"},
                    "backgroundColor": "#e8f5e9",
                },
                {
                    "if": {"filter_query": "{load_growth_pct} < -5"},
                    "backgroundColor": "#ffebee",
                },
            ],
        ),

        # Section 2: Monthly load — absolute vs indexed
        html.H3("Monthly Load", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Absolute load (MWh)"),
                        dcc.Graph(id="cc-load-abs-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Indexed load (first month = 100)"),
                        dcc.Graph(id="cc-load-indexed-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 3: Net flows comparison
        html.H3("Net Cross-Border Flows", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Monthly net flows"),
                        dcc.Graph(id="cc-netflow-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("YoY load change (%)"),
                        dcc.Graph(id="cc-yoy-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 4: Structural comparison (radar)
        html.H3("Structural Comparison", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Load profile comparison (monthly distribution)"),
                        dcc.Graph(id="cc-seasonal-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Peak demand comparison"),
                        dcc.Graph(id="cc-peak-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),
    ]
)

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

@callback(
    Output("cc-summary-table", "data"),
    Output("cc-summary-table", "columns"),
    Output("cc-load-abs-graph", "figure"),
    Output("cc-load-indexed-graph", "figure"),
    Output("cc-netflow-graph", "figure"),
    Output("cc-yoy-graph", "figure"),
    Output("cc-seasonal-graph", "figure"),
    Output("cc-peak-graph", "figure"),
    Input("cc-countries", "value"),
    Input("cc-date-range", "start_date"),
    Input("cc-date-range", "end_date"),
)
def update_comparison(countries, start_date, end_date):
    empty_fig = go.Figure()

    if not countries or not start_date or not end_date:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    # Limit to 6 countries for readability
    countries = countries[:6]

    # --- Summary table ---
    df_stats = get_country_comparison_stats(countries, start_date, end_date)

    if df_stats.empty:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    table_columns = [
        {"name": "Country", "id": "country"},
        {"name": "Total load (TWh)", "id": "total_load_twh"},
        {"name": "Avg monthly (GWh)", "id": "avg_monthly_gwh"},
        {"name": "Peak (MW)", "id": "peak_mw"},
        {"name": "Load growth (%)", "id": "load_growth_pct"},
        {"name": "Volatility (CV)", "id": "volatility_cv"},
        {"name": "Renew. share (%)", "id": "renewable_share_pct"},
        {"name": "Trade position", "id": "net_position"},
    ]
    table_data = df_stats.to_dict("records")

    # --- Absolute load chart ---
    load_frames = []
    for country in countries:
        df_c = get_monthly_load(country, start_date, end_date)
        if df_c.empty:
            continue
        df_c = df_c.copy()
        df_c["country"] = country
        load_frames.append(df_c)

    if load_frames:
        df_load = pd.concat(load_frames, ignore_index=True)

        fig_abs = px.line(
            df_load,
            x="year_month",
            y="load_sum",
            color="country",
            labels={"year_month": "Month", "load_sum": "Monthly load (MWh)", "country": "Country"},
            title="Monthly load — absolute",
        )
    else:
        fig_abs = empty_fig

    # --- Indexed load chart ---
    df_indexed = get_indexed_load(countries, start_date, end_date)

    if df_indexed.empty:
        fig_indexed = empty_fig
    else:
        fig_indexed = px.line(
            df_indexed,
            x="year_month",
            y="indexed_load",
            color="country",
            labels={"year_month": "Month", "indexed_load": "Indexed load (base=100)", "country": "Country"},
            title="Monthly load — indexed (start = 100)",
        )
        fig_indexed.add_hline(y=100, line_dash="dash", line_color="gray")

    # --- Net flows comparison ---
    flow_frames = []
    for country in countries:
        df_f = get_net_country_flows(country, start_date, end_date)
        if df_f.empty:
            continue
        df_f = df_f.copy()
        df_f["country"] = country
        flow_frames.append(df_f)

    if flow_frames:
        df_flows = pd.concat(flow_frames, ignore_index=True)

        fig_flows = px.line(
            df_flows,
            x="date",
            y="net_flow",
            color="country",
            labels={"date": "Month", "net_flow": "Net imports (+) / exports (−)", "country": "Country"},
            title="Net cross-border flows",
        )
        fig_flows.add_hline(y=0, line_dash="dash", line_color="gray")
    else:
        fig_flows = empty_fig

    # --- YoY load change ---
    df_yoy = get_yoy_load_comparison(countries, start_date, end_date)

    if df_yoy.empty:
        fig_yoy = empty_fig
    else:
        fig_yoy = px.bar(
            df_yoy,
            x="year",
            y="yoy_pct",
            color="country",
            barmode="group",
            labels={"year": "Year", "yoy_pct": "YoY change (%)", "country": "Country"},
            title="Year-over-year load change",
        )
        fig_yoy.add_hline(y=0, line_dash="dash", line_color="gray")

    # --- Seasonal profile (avg load by calendar month, normalized) ---
    if load_frames:
        df_all_load = pd.concat(load_frames, ignore_index=True)
        df_all_load["month"] = df_all_load["year_month"].dt.month

        # Normalize each country's monthly avg to its own mean (seasonal shape comparison)
        seasonal_frames = []
        for country in countries:
            df_c = df_all_load[df_all_load["country"] == country]
            monthly_avg = df_c.groupby("month")["load_sum"].mean().reset_index()
            country_mean = monthly_avg["load_sum"].mean()
            monthly_avg["seasonal_index"] = (monthly_avg["load_sum"] / country_mean) * 100 if country_mean > 0 else 100
            monthly_avg["country"] = country
            seasonal_frames.append(monthly_avg)

        df_seasonal = pd.concat(seasonal_frames, ignore_index=True)

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        df_seasonal["month_name"] = df_seasonal["month"].apply(lambda m: month_names[m - 1])

        fig_seasonal = px.line(
            df_seasonal,
            x="month_name",
            y="seasonal_index",
            color="country",
            markers=True,
            labels={"month_name": "Month", "seasonal_index": "Seasonal index (avg=100)", "country": "Country"},
            title="Seasonal load shape (each country normalized to own average)",
            category_orders={"month_name": month_names},
        )
        fig_seasonal.add_hline(y=100, line_dash="dot", line_color="gray")
    else:
        fig_seasonal = empty_fig

    # --- Peak demand comparison (annual peaks bar chart) ---
    if load_frames:
        df_all_load2 = pd.concat(load_frames, ignore_index=True)
        df_all_load2["year"] = df_all_load2["year_month"].dt.year

        annual_peaks = (
            df_all_load2.groupby(["country", "year"])["load_peak"]
            .max()
            .reset_index()
        )

        fig_peak = px.line(
            annual_peaks,
            x="year",
            y="load_peak",
            color="country",
            markers=True,
            labels={"year": "Year", "load_peak": "Annual peak demand (MW)", "country": "Country"},
            title="Annual peak demand trend",
        )
    else:
        fig_peak = empty_fig

    return (
        table_data, table_columns, fig_abs, fig_indexed,
        fig_flows, fig_yoy, fig_seasonal, fig_peak
    )
