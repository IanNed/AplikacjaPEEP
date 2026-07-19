import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_monthly,
    get_monthly_load_clean,
    get_net_country_flows,
    get_indexed_load,
    get_country_comparison_stats,
    get_yoy_load_comparison,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/compare-countries",
    name="Porównanie krajów",
    title="Porównanie krajów",
)

# Preload monthly data to get countries and date range
_monthly_df = load_monthly()
COUNTRIES = sorted(_monthly_df["country"].unique())

COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_monthly_df["country"].unique())
]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Porównanie krajów",
        "Porównanie wielu krajów w ujęciu bezwzględnym i znormalizowanym. "
        "Indeksowane obciążenie (baza=100) umożliwia rzetelne porównanie krajów o różnej wielkości."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraje (wybierz 2-6)", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="cc-countries",
                    options=COUNTRY_OPTIONS,
                    value=["DE", "FR", "PL", "ES", "IT"],
                    multi=True,
                    clearable=False,
                ),
            ], md=7),
            dbc.Col([
                dbc.Label("Zakres dat", style={"color": "#ccc"}),
                dcc.DatePickerRange(
                    id="cc-date-range",
                    min_date_allowed=MIN_DATE,
                    max_date_allowed=MAX_DATE,
                    start_date=MIN_DATE,
                    end_date=MAX_DATE,
                    display_format="YYYY-MM",
                ),
            ], md=5),
        ]),
    ),

    # Section 1: Summary comparison table
    section_header("Podsumowanie porównawcze"),
    dash_table.DataTable(
        id="cc-summary-table",
        columns=[],
        data=[],
        sort_action="native",
        style_table=DARK_TABLE_STYLE["style_table"],
        style_cell=DARK_TABLE_STYLE["style_cell"],
        style_header=DARK_TABLE_STYLE["style_header"],
        style_data_conditional=[
            *DARK_TABLE_STYLE["style_data_conditional"],
            {"if": {"filter_query": "{load_growth_pct} > 5"}, "backgroundColor": "#1a3a2a", "color": "#6bcf7f"},
            {"if": {"filter_query": "{load_growth_pct} < -5"}, "backgroundColor": "#3a1a1a", "color": "#ff6b6b"},
        ],
    ),

    # Section 2: Monthly load — absolute vs indexed
    section_header("Obciążenie miesięczne"),
    dbc.Row([
        dbc.Col(chart_card("Obciążenie bezwzględne (MWh)", "cc-load-abs-graph"), md=6),
        dbc.Col(chart_card("Obciążenie indeksowane (pierwszy miesiąc = 100)", "cc-load-indexed-graph"), md=6),
    ]),

    # Section 3: Net flows + YoY
    section_header("Przepływy transgraniczne netto"),
    dbc.Row([
        dbc.Col(chart_card("Miesięczne przepływy netto", "cc-netflow-graph"), md=6),
        dbc.Col(chart_card("Zmiana obciążenia r/r (%)", "cc-yoy-graph"), md=6),
    ]),

    # Section 4: Structural comparison
    section_header("Porównanie cech strukturalnych"),
    dbc.Row([
        dbc.Col(chart_card("Rozkład sezonowy (wg miesiąca)", "cc-seasonal-graph"), md=6),
        dbc.Col(chart_card("Porównanie szczytowego zapotrzebowania", "cc-peak-graph"), md=6),
    ]),
])

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

    countries = countries[:6]

    # --- Summary table ---
    df_stats = get_country_comparison_stats(countries, start_date, end_date)

    if df_stats.empty:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    # Map country codes to names in table
    df_stats = df_stats.copy()
    df_stats["kraj"] = df_stats["country"].map(COUNTRY_NAMES_PL)

    table_columns = [
        {"name": "Kraj", "id": "kraj"},
        {"name": "Obciążenie łączne (TWh)", "id": "total_load_twh"},
        {"name": "Śr. miesięczne (GWh)", "id": "avg_monthly_gwh"},
        {"name": "Szczyt (MW)", "id": "peak_mw"},
        {"name": "Wzrost obciążenia (%)", "id": "load_growth_pct"},
        {"name": "Zmienność (CV)", "id": "volatility_cv"},
        {"name": "Udział OZE (%)", "id": "renewable_share_pct"},
        {"name": "Pozycja handlowa", "id": "net_position"},
    ]
    table_data = df_stats.to_dict("records")

    # --- Absolute load chart ---
    load_frames = []
    for country in countries:
        df_c = get_monthly_load_clean(country, start_date, end_date)
        if df_c.empty:
            continue
        df_c = df_c.copy()
        df_c["country_name"] = COUNTRY_NAMES_PL.get(country, country)
        load_frames.append(df_c)

    if load_frames:
        df_load = pd.concat(load_frames, ignore_index=True)

        fig_abs = px.line(
            df_load,
            x="year_month",
            y="load_sum",
            color="country_name",
            labels={"year_month": "Miesiąc", "load_sum": "Obciążenie miesięczne (MWh)", "country_name": "Kraj"},
            title="Obciążenie miesięczne — bezwzględne",
        )
    else:
        fig_abs = empty_fig

    # --- Indexed load chart ---
    df_indexed = get_indexed_load(countries, start_date, end_date)

    if df_indexed.empty:
        fig_indexed = empty_fig
    else:
        df_indexed = df_indexed.copy()
        df_indexed["country_name"] = df_indexed["country"].map(COUNTRY_NAMES_PL)

        fig_indexed = px.line(
            df_indexed,
            x="year_month",
            y="indexed_load",
            color="country_name",
            labels={"year_month": "Miesiąc", "indexed_load": "Obciążenie indeksowane (baza=100)", "country_name": "Kraj"},
            title="Obciążenie miesięczne — indeksowane (start = 100)",
        )
        fig_indexed.add_hline(y=100, line_dash="dash", line_color="rgba(255,255,255,0.3)")

    # --- Net flows comparison ---
    flow_frames = []
    for country in countries:
        df_f = get_net_country_flows(country, start_date, end_date)
        if df_f.empty:
            continue
        df_f = df_f.copy()
        df_f["country_name"] = COUNTRY_NAMES_PL.get(country, country)
        flow_frames.append(df_f)

    if flow_frames:
        df_flows = pd.concat(flow_frames, ignore_index=True)

        fig_flows = px.line(
            df_flows,
            x="date",
            y="net_flow",
            color="country_name",
            labels={"date": "Miesiąc", "net_flow": "Import netto (+) / eksport (−)", "country_name": "Kraj"},
            title="Przepływy transgraniczne netto",
        )
        fig_flows.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    else:
        fig_flows = empty_fig

    # --- YoY load change ---
    df_yoy = get_yoy_load_comparison(countries, start_date, end_date)

    if df_yoy.empty:
        fig_yoy = empty_fig
    else:
        df_yoy = df_yoy.copy()
        df_yoy["country_name"] = df_yoy["country"].map(COUNTRY_NAMES_PL)

        fig_yoy = px.bar(
            df_yoy,
            x="year",
            y="yoy_pct",
            color="country_name",
            barmode="group",
            labels={"year": "Rok", "yoy_pct": "Zmiana r/r (%)", "country_name": "Kraj"},
            title="Zmiana obciążenia rok do roku",
        )
        fig_yoy.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")

    # --- Seasonal profile (normalized) ---
    if load_frames:
        df_all_load = pd.concat(load_frames, ignore_index=True)
        df_all_load["month"] = df_all_load["year_month"].dt.month

        seasonal_frames = []
        for country in countries:
            c_name = COUNTRY_NAMES_PL.get(country, country)
            df_c = df_all_load[df_all_load["country_name"] == c_name]
            monthly_avg = df_c.groupby("month")["load_sum"].mean().reset_index()
            country_mean = monthly_avg["load_sum"].mean()
            monthly_avg["seasonal_index"] = (monthly_avg["load_sum"] / country_mean) * 100 if country_mean > 0 else 100
            monthly_avg["country_name"] = c_name
            seasonal_frames.append(monthly_avg)

        df_seasonal = pd.concat(seasonal_frames, ignore_index=True)

        month_names = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze",
                       "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]
        df_seasonal["month_name"] = df_seasonal["month"].apply(lambda m: month_names[m - 1])

        fig_seasonal = px.line(
            df_seasonal,
            x="month_name",
            y="seasonal_index",
            color="country_name",
            markers=True,
            labels={"month_name": "Miesiąc", "seasonal_index": "Indeks sezonowy (śr.=100)", "country_name": "Kraj"},
            title="Kształt sezonowy (każdy kraj znormalizowany do własnej średniej)",
            category_orders={"month_name": month_names},
        )
        fig_seasonal.add_hline(y=100, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    else:
        fig_seasonal = empty_fig

    # --- Peak demand comparison ---
    if load_frames:
        df_all_load2 = pd.concat(load_frames, ignore_index=True)
        df_all_load2["year"] = df_all_load2["year_month"].dt.year

        annual_peaks = (
            df_all_load2.groupby(["country_name", "year"])["load_peak"]
            .max()
            .reset_index()
        )

        fig_peak = px.line(
            annual_peaks,
            x="year",
            y="load_peak",
            color="country_name",
            markers=True,
            labels={"year": "Rok", "load_peak": "Roczny szczyt zapotrzebowania (MW)", "country_name": "Kraj"},
            title="Trend szczytowego zapotrzebowania",
        )
    else:
        fig_peak = empty_fig

    return (
        table_data, table_columns, fig_abs, fig_indexed,
        fig_flows, fig_yoy, fig_seasonal, fig_peak
    )
