import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import pandas as pd

from app.backend.data_access import (
    load_monthly,
    get_seasonal_decomposition,
    get_seasonal_strength,
    get_anomaly_months,
)

dash.register_page(
    __name__,
    path="/seasonality",
    name="Seasonality decomposition",
    title="Seasonality decomposition",
)

# Preload monthly data for country list and date bounds
_monthly_df = load_monthly()

COUNTRY_OPTIONS = [
    {"label": c, "value": c}
    for c in sorted(_monthly_df["country"].unique())
]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()


layout = html.Div(
    [
        html.H2("Seasonality & Trend Decomposition (STL)"),
        html.P(
            "Decomposes monthly electricity load into trend, seasonal, and residual "
            "components using STL (Seasonal-Trend decomposition using LOESS). "
            "Requires at least 24 months of data for meaningful results.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="sd-country",
                            options=COUNTRY_OPTIONS,
                            value="DE",
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Date range"),
                        dcc.DatePickerRange(
                            id="sd-date-range",
                            min_date_allowed=MIN_DATE,
                            max_date_allowed=MAX_DATE,
                            start_date=MIN_DATE,
                            end_date=MAX_DATE,
                            display_format="YYYY-MM",
                        ),
                    ],
                    style={"width": "60%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        # KPI cards
        html.Div(
            id="sd-kpis",
            style={"marginBottom": "2rem"},
        ),

        # Main decomposition chart (4 subplots)
        html.H4("Decomposition components"),
        dcc.Graph(id="sd-decomposition-graph"),

        # Seasonal pattern (average by month)
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Average seasonal pattern"),
                        dcc.Graph(id="sd-seasonal-pattern-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Trend growth rate (YoY %)"),
                        dcc.Graph(id="sd-trend-growth-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),

        # Anomaly table
        html.H4("Detected anomalies (|z-score| > 2)"),
        html.P(
            "Months where actual load deviated significantly from expected (trend + season). "
            "Look for events like COVID lockdowns, heatwaves, or energy crises.",
            style={"color": "#555", "fontSize": "0.9rem"},
        ),
        dash_table.DataTable(
            id="sd-anomaly-table",
            columns=[],
            data=[],
            page_size=10,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
            style_header={"fontWeight": "bold"},
            style_data_conditional=[
                {
                    "if": {"filter_query": "{residual_zscore} > 2"},
                    "backgroundColor": "#ffe0e0",
                },
                {
                    "if": {"filter_query": "{residual_zscore} < -2"},
                    "backgroundColor": "#e0e8ff",
                },
            ],
        ),
    ]
)


@callback(
    Output("sd-kpis", "children"),
    Output("sd-decomposition-graph", "figure"),
    Output("sd-seasonal-pattern-graph", "figure"),
    Output("sd-trend-growth-graph", "figure"),
    Output("sd-anomaly-table", "data"),
    Output("sd-anomaly-table", "columns"),
    Input("sd-country", "value"),
    Input("sd-date-range", "start_date"),
    Input("sd-date-range", "end_date"),
)
def update_seasonality(country, start_date, end_date):
    empty_fig = go.Figure()

    if not country or not start_date or not end_date:
        return html.Div(), empty_fig, empty_fig, empty_fig, [], []

    # Run STL decomposition
    df = get_seasonal_decomposition(country, start_date, end_date)

    if df.empty:
        msg = html.Div(
            "Not enough data for decomposition (need at least 24 months).",
            style={"color": "red", "fontWeight": "bold"},
        )
        return msg, empty_fig, empty_fig, empty_fig, [], []

    # --- KPIs ---
    seasonal_strength = get_seasonal_strength(country, start_date, end_date)

    # Trend direction: compare first 6 months of trend to last 6 months
    trend_start = df["trend"].iloc[:6].mean()
    trend_end = df["trend"].iloc[-6:].mean()
    trend_change_pct = ((trend_end - trend_start) / trend_start) * 100 if trend_start != 0 else 0

    # Seasonal amplitude (peak-to-trough range as % of mean load)
    seasonal_amplitude = df["seasonal"].max() - df["seasonal"].min()
    mean_load = df["load_sum"].mean()
    seasonal_pct = (seasonal_amplitude / mean_load) * 100 if mean_load != 0 else 0

    # Number of anomalies
    anomalies = get_anomaly_months(country, start_date, end_date, threshold=2.0)
    n_anomalies = len(anomalies)

    kpi_children = html.Div(
        style={"display": "flex", "gap": "2rem", "flexWrap": "wrap"},
        children=[
            _kpi_card("Seasonal Strength", f"{seasonal_strength:.3f}", _strength_label(seasonal_strength)),
            _kpi_card("Trend Change", f"{trend_change_pct:+.1f}%", "start-of-period vs end-of-period"),
            _kpi_card("Seasonal Amplitude", f"{seasonal_pct:.1f}%", "peak-to-trough as % of mean load"),
            _kpi_card("Anomalies Detected", str(n_anomalies), "months with |z| > 2"),
        ],
    )

    # --- Main decomposition subplot ---
    fig_decomp = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("Original (monthly load)", "Trend", "Seasonal", "Residual"),
    )

    # Original
    fig_decomp.add_trace(
        go.Scatter(
            x=df["year_month"], y=df["load_sum"],
            mode="lines", name="Original",
            line=dict(color="#1f77b4"),
        ),
        row=1, col=1,
    )

    # Trend
    fig_decomp.add_trace(
        go.Scatter(
            x=df["year_month"], y=df["trend"],
            mode="lines", name="Trend",
            line=dict(color="#ff7f0e", width=2),
        ),
        row=2, col=1,
    )

    # Seasonal
    fig_decomp.add_trace(
        go.Scatter(
            x=df["year_month"], y=df["seasonal"],
            mode="lines", name="Seasonal",
            line=dict(color="#2ca02c"),
        ),
        row=3, col=1,
    )

    # Residual
    fig_decomp.add_trace(
        go.Bar(
            x=df["year_month"], y=df["residual"],
            name="Residual",
            marker_color=df["residual"].apply(
                lambda v: "#d62728" if abs(v) > 2 * df["residual"].std() else "#9467bd"
            ),
        ),
        row=4, col=1,
    )

    fig_decomp.update_layout(
        height=700,
        showlegend=False,
        title_text=f"STL Decomposition — {country}",
        margin=dict(t=60),
    )
    fig_decomp.update_yaxes(title_text="MWh", row=1, col=1)
    fig_decomp.update_yaxes(title_text="MWh", row=2, col=1)
    fig_decomp.update_yaxes(title_text="MWh", row=3, col=1)
    fig_decomp.update_yaxes(title_text="MWh", row=4, col=1)
    fig_decomp.update_xaxes(title_text="Month", row=4, col=1)

    # --- Average seasonal pattern (by calendar month) ---
    df_seasonal = df.copy()
    df_seasonal["month"] = df_seasonal["year_month"].dt.month

    monthly_avg = (
        df_seasonal.groupby("month")["seasonal"]
        .mean()
        .reset_index()
    )

    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    monthly_avg["month_name"] = monthly_avg["month"].apply(lambda m: month_names[m - 1])

    fig_pattern = px.bar(
        monthly_avg,
        x="month_name",
        y="seasonal",
        labels={"month_name": "Month", "seasonal": "Seasonal component (MWh)"},
        title=f"Average seasonal pattern — {country}",
        color="seasonal",
        color_continuous_scale=["#2196F3", "#FFC107", "#FF5722"],
    )
    fig_pattern.update_layout(
        xaxis=dict(categoryorder="array", categoryarray=month_names),
        coloraxis_showscale=False,
    )

    # --- Trend growth rate (YoY %) ---
    df_trend = df[["year_month", "trend"]].copy()
    df_trend["trend_12m_ago"] = df_trend["trend"].shift(12)
    df_trend["yoy_pct"] = (
        (df_trend["trend"] - df_trend["trend_12m_ago"]) / df_trend["trend_12m_ago"] * 100
    )
    df_trend = df_trend.dropna(subset=["yoy_pct"])

    fig_growth = px.line(
        df_trend,
        x="year_month",
        y="yoy_pct",
        markers=True,
        labels={"year_month": "Month", "yoy_pct": "YoY trend change (%)"},
        title=f"Trend growth rate (year-over-year) — {country}",
    )
    fig_growth.add_hline(y=0, line_dash="dash", line_color="gray")

    # --- Anomaly table ---
    if anomalies.empty:
        table_data = []
        table_columns = []
    else:
        anomalies_view = anomalies.copy()
        anomalies_view["year_month"] = anomalies_view["year_month"].dt.strftime("%Y-%m")
        anomalies_view["residual"] = anomalies_view["residual"].round(0)
        anomalies_view["residual_zscore"] = anomalies_view["residual_zscore"].round(2)
        anomalies_view["load_sum"] = anomalies_view["load_sum"].round(0)

        table_columns = [
            {"name": "Month", "id": "year_month"},
            {"name": "Actual load (MWh)", "id": "load_sum"},
            {"name": "Residual (MWh)", "id": "residual"},
            {"name": "Z-score", "id": "residual_zscore"},
        ]
        table_data = anomalies_view.to_dict("records")

    return kpi_children, fig_decomp, fig_pattern, fig_growth, table_data, table_columns


# --- Helper functions ---

def _kpi_card(title: str, value: str, subtitle: str):
    return html.Div(
        [
            html.Div(title, style={"fontSize": "0.85rem", "color": "#666"}),
            html.Div(value, style={"fontSize": "1.5rem", "fontWeight": "bold"}),
            html.Div(subtitle, style={"fontSize": "0.75rem", "color": "#999"}),
        ],
        style={
            "flex": "1",
            "minWidth": "150px",
            "padding": "1rem",
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
            "textAlign": "center",
            "backgroundColor": "#fafafa",
        },
    )


def _strength_label(strength):
    if strength is None:
        return "N/A"
    if strength >= 0.8:
        return "Very strong seasonality"
    elif strength >= 0.6:
        return "Strong seasonality"
    elif strength >= 0.4:
        return "Moderate seasonality"
    elif strength >= 0.2:
        return "Weak seasonality"
    else:
        return "Very weak / no seasonality"
