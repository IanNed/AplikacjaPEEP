import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_monthly,
    get_seasonal_decomposition,
    get_seasonal_strength,
    get_anomaly_months,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card, kpi_card, kpi_row,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/seasonality",
    name="Sezonowość",
    title="Dekompozycja sezonowości",
)

# Preload monthly data for country list and date bounds
_monthly_df = load_monthly()

COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_monthly_df["country"].unique())
]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()

# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------

def _strength_label(strength):
    if strength is None:
        return "N/A"
    if strength >= 0.8:
        return "Bardzo silna sezonowość"
    elif strength >= 0.6:
        return "Silna sezonowość"
    elif strength >= 0.4:
        return "Umiarkowana sezonowość"
    elif strength >= 0.2:
        return "Słaba sezonowość"
    else:
        return "Bardzo słaba / brak sezonowości"

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Dekompozycja sezonowości i trendu (STL)",
        "Rozkłada miesięczne obciążenie elektryczne na składowe: trend, sezonowość "
        "i reszty przy użyciu metody STL (Seasonal-Trend decomposition using LOESS). "
        "Wymaga co najmniej 24 miesięcy danych."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraj", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="sd-country",
                    options=COUNTRY_OPTIONS,
                    value="PL",
                    clearable=False,
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Zakres dat", style={"color": "#ccc"}),
                dcc.DatePickerRange(
                    id="sd-date-range",
                    min_date_allowed=MIN_DATE,
                    max_date_allowed=MAX_DATE,
                    start_date=MIN_DATE,
                    end_date=MAX_DATE,
                    display_format="YYYY-MM",
                ),
            ], md=8),
        ]),
    ),

    # KPI cards
    html.Div(id="sd-kpis", className="mb-4"),

    # Main decomposition chart
    section_header("Składowe dekompozycji"),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="sd-decomposition-graph", style={"height": "700px"}),
            style={"padding": "0.5rem"},
        ),
        className="mb-4",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),

    # Seasonal pattern + Trend growth
    dbc.Row([
        dbc.Col(chart_card("Średni wzorzec sezonowy", "sd-seasonal-pattern-graph"), md=6),
        dbc.Col(chart_card("Tempo wzrostu trendu (r/r %)", "sd-trend-growth-graph"), md=6),
    ]),

    # Anomaly table
    section_header(
        "Wykryte anomalie (|z-score| > 2)",
        "Miesiące, w których rzeczywiste obciążenie znacząco odbiega od oczekiwanego (trend + sezon). "
        "Szukaj wydarzeń: lockdowny COVID, fale upałów, kryzysy energetyczne."
    ),
    dash_table.DataTable(
        id="sd-anomaly-table",
        columns=[],
        data=[],
        page_size=10,
        sort_action="native",
        style_table=DARK_TABLE_STYLE["style_table"],
        style_cell=DARK_TABLE_STYLE["style_cell"],
        style_header=DARK_TABLE_STYLE["style_header"],
        style_data_conditional=[
            *DARK_TABLE_STYLE["style_data_conditional"],
            {"if": {"filter_query": "{residual_zscore} > 2"}, "backgroundColor": "#3a1a1a", "color": "#ff6b6b"},
            {"if": {"filter_query": "{residual_zscore} < -2"}, "backgroundColor": "#1a1a3a", "color": "#3391ff"},
        ],
    ),
])

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

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

    country_name = COUNTRY_NAMES_PL.get(country, country)

    # Run STL decomposition
    df = get_seasonal_decomposition(country, start_date, end_date)

    if df.empty:
        msg = html.Div(
            "Niewystarczająca ilość danych do dekompozycji (wymagane co najmniej 24 miesiące).",
            style={"color": "#ff6b6b", "fontWeight": "bold", "padding": "1rem"},
        )
        return msg, empty_fig, empty_fig, empty_fig, [], []

    # --- KPIs ---
    seasonal_strength = get_seasonal_strength(country, start_date, end_date)

    trend_start = df["trend"].iloc[:6].mean()
    trend_end = df["trend"].iloc[-6:].mean()
    trend_change_pct = ((trend_end - trend_start) / trend_start) * 100 if trend_start != 0 else 0

    seasonal_amplitude = df["seasonal"].max() - df["seasonal"].min()
    mean_load = df["load_sum"].mean()
    seasonal_pct = (seasonal_amplitude / mean_load) * 100 if mean_load != 0 else 0

    anomalies = get_anomaly_months(country, start_date, end_date, threshold=2.0)
    n_anomalies = len(anomalies)

    if seasonal_strength >= 0.6:
        strength_color = "#00d4aa"
    elif seasonal_strength >= 0.4:
        strength_color = "#ffd93d"
    else:
        strength_color = "#ff6b6b"

    trend_color = "#00d4aa" if trend_change_pct > 0 else "#ff6b6b"

    kpi_children = kpi_row([
        kpi_card("Siła sezonowości", f"{seasonal_strength:.3f}", _strength_label(seasonal_strength), value_color=strength_color),
        kpi_card("Zmiana trendu", f"{trend_change_pct:+.1f}%", "początek vs koniec okresu", value_color=trend_color),
        kpi_card("Amplituda sezonowa", f"{seasonal_pct:.1f}%", "szczyt–dół jako % śr. obciążenia", value_color="#3391ff"),
        kpi_card("Wykryte anomalie", str(n_anomalies), "miesiące z |z| > 2", value_color="#f97316" if n_anomalies > 3 else "#00d4aa"),
    ])

    # --- Main decomposition subplot ---
    fig_decomp = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("Oryginał (obciążenie miesięczne)", "Trend", "Sezonowość", "Reszty"),
    )

    fig_decomp.add_trace(
        go.Scatter(
            x=df["year_month"], y=df["load_sum"],
            mode="lines", name="Oryginał",
            line=dict(color="#3391ff"),
        ),
        row=1, col=1,
    )

    fig_decomp.add_trace(
        go.Scatter(
            x=df["year_month"], y=df["trend"],
            mode="lines", name="Trend",
            line=dict(color="#f97316", width=2),
        ),
        row=2, col=1,
    )

    fig_decomp.add_trace(
        go.Scatter(
            x=df["year_month"], y=df["seasonal"],
            mode="lines", name="Sezonowość",
            line=dict(color="#00d4aa"),
        ),
        row=3, col=1,
    )

    fig_decomp.add_trace(
        go.Bar(
            x=df["year_month"], y=df["residual"],
            name="Reszty",
            marker_color=df["residual"].apply(
                lambda v: "#ff6b6b" if abs(v) > 2 * df["residual"].std() else "#a78bfa"
            ),
        ),
        row=4, col=1,
    )

    fig_decomp.update_layout(
        height=700,
        showlegend=False,
        title_text=f"Dekompozycja STL — {country_name}",
        margin=dict(t=60),
    )
    fig_decomp.update_yaxes(title_text="MWh", row=1, col=1)
    fig_decomp.update_yaxes(title_text="MWh", row=2, col=1)
    fig_decomp.update_yaxes(title_text="MWh", row=3, col=1)
    fig_decomp.update_yaxes(title_text="MWh", row=4, col=1)
    fig_decomp.update_xaxes(title_text="Miesiąc", row=4, col=1)

    # --- Average seasonal pattern (by calendar month) ---
    df_seasonal = df.copy()
    df_seasonal["month"] = df_seasonal["year_month"].dt.month

    monthly_avg = (
        df_seasonal.groupby("month")["seasonal"]
        .mean()
        .reset_index()
    )

    month_names = [
        "Sty", "Lut", "Mar", "Kwi", "Maj", "Cze",
        "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru",
    ]
    monthly_avg["month_name"] = monthly_avg["month"].apply(lambda m: month_names[m - 1])

    fig_pattern = px.bar(
        monthly_avg,
        x="month_name",
        y="seasonal",
        labels={"month_name": "Miesiąc", "seasonal": "Składowa sezonowa (MWh)"},
        title=f"Średni wzorzec sezonowy — {country_name}",
        color="seasonal",
        color_continuous_scale=["#3391ff", "#ffd93d", "#ff6b6b"],
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
        labels={"year_month": "Miesiąc", "yoy_pct": "Zmiana trendu r/r (%)"},
        title=f"Tempo wzrostu trendu (rok do roku) — {country_name}",
    )
    fig_growth.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")

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
            {"name": "Miesiąc", "id": "year_month"},
            {"name": "Rzeczywiste obciążenie (MWh)", "id": "load_sum"},
            {"name": "Reszta (MWh)", "id": "residual"},
            {"name": "Z-score", "id": "residual_zscore"},
        ]
        table_data = anomalies_view.to_dict("records")

    return kpi_children, fig_decomp, fig_pattern, fig_growth, table_data, table_columns
