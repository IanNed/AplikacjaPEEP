import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_year_bounds,
    get_self_sufficiency,
    get_self_sufficiency_comparison,
)

dash.register_page(
    __name__,
    path="/self-sufficiency",
    name="Self-sufficiency",
    title="Self-sufficiency & import dependency",
)

# -----------------------------------------------------------------------
# Data setup
# -----------------------------------------------------------------------

_eu_df = load_eurostat_share_annual()

COUNTRIES = sorted(_eu_df["country"].unique())
COUNTRY_OPTIONS = [{"label": c, "value": c} for c in COUNTRIES]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div(
    [
        html.H2("Self-Sufficiency & Import Dependency"),
        html.P(
            "Combines domestic generation (Eurostat), electricity load (ENTSO-E), and "
            "cross-border flows (ENTSO-E) to assess how well a country can meet its own "
            "demand — and whether renewables growth is reducing import reliance.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Countries"),
                        dcc.Dropdown(
                            id="ss-countries",
                            options=COUNTRY_OPTIONS,
                            value=["DE", "PL", "FR", "IT", "ES"],
                            multi=True,
                            clearable=False,
                        ),
                    ],
                    style={"width": "55%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Year range"),
                        dcc.RangeSlider(
                            id="ss-year-range",
                            min=MIN_YEAR,
                            max=MAX_YEAR,
                            value=[MIN_YEAR, MAX_YEAR],
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                            allowCross=False,
                        ),
                    ],
                    style={"width": "40%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        # Section 1: KPI comparison (latest year)
        html.H3("Latest-Year Comparison", style={"marginTop": "1rem"}),
        html.P(
            "Self-sufficiency > 1 = net producer. Import dependency shows what fraction of "
            "load is covered by net imports. Renewable self-sufficiency shows how much of "
            "demand is met by domestic renewables alone.",
            style={"color": "#666", "fontSize": "0.9rem"},
        ),
        dash_table.DataTable(
            id="ss-comparison-table",
            columns=[],
            data=[],
            page_size=15,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "8px"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f0f0f0"},
            style_data_conditional=[
                {
                    "if": {"filter_query": "{self_sufficiency_ratio} >= 1"},
                    "backgroundColor": "#e8f5e9",
                },
                {
                    "if": {"filter_query": "{self_sufficiency_ratio} < 1"},
                    "backgroundColor": "#fff3e0",
                },
                {
                    "if": {"filter_query": "{import_dependency} > 0.2"},
                    "color": "#d32f2f",
                },
            ],
        ),

        # Section 2: Time series — self-sufficiency ratio
        html.H3("Self-Sufficiency Over Time", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Self-sufficiency ratio (generation / load)"),
                        dcc.Graph(id="ss-ratio-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Import dependency (net imports / load)"),
                        dcc.Graph(id="ss-import-dep-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 3: Renewable coverage
        html.H3("Renewable Self-Sufficiency", style={"marginTop": "2rem"}),
        html.P(
            "What fraction of total demand can be met by domestic renewable generation? "
            "Rising values indicate renewables are displacing both fossil and imports.",
            style={"color": "#666", "fontSize": "0.9rem"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Renewable generation vs load coverage"),
                        dcc.Graph(id="ss-renewable-coverage-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Energy balance breakdown"),
                        dcc.Graph(id="ss-balance-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 4: Detailed country view
        html.H3("Detailed Annual Data", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Label("Select single country for detail"),
                dcc.Dropdown(
                    id="ss-detail-country",
                    options=COUNTRY_OPTIONS,
                    value="DE",
                    clearable=False,
                    style={"width": "200px"},
                ),
            ],
            style={"marginBottom": "1rem"},
        ),
        dash_table.DataTable(
            id="ss-detail-table",
            columns=[],
            data=[],
            page_size=12,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "6px", "fontSize": "0.85rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f0f0f0"},
        ),
    ]
)

# -----------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------

@callback(
    Output("ss-comparison-table", "data"),
    Output("ss-comparison-table", "columns"),
    Output("ss-ratio-graph", "figure"),
    Output("ss-import-dep-graph", "figure"),
    Output("ss-renewable-coverage-graph", "figure"),
    Output("ss-balance-graph", "figure"),
    Input("ss-countries", "value"),
    Input("ss-year-range", "value"),
)
def update_self_sufficiency(countries, year_range):
    empty_fig = go.Figure()

    if not countries or not year_range:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    # --- Comparison table (latest year) ---
    df_comp = get_self_sufficiency_comparison(countries, start_year, end_year)

    if df_comp.empty:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    comp_columns = [
        {"name": "Country", "id": "country"},
        {"name": "Year", "id": "year"},
        {"name": "Self-sufficiency", "id": "self_sufficiency_ratio"},
        {"name": "Import dependency", "id": "import_dependency"},
        {"name": "Renewable self-suff.", "id": "renewable_self_sufficiency"},
        {"name": "Export surplus", "id": "export_surplus"},
    ]
    comp_data = df_comp.to_dict("records")

    # --- Time series charts (all selected countries) ---
    all_frames = []
    for country in countries:
        df = get_self_sufficiency(country)
        if df.empty:
            continue
        df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()
        df["country"] = country
        all_frames.append(df)

    if not all_frames:
        return comp_data, comp_columns, empty_fig, empty_fig, empty_fig, empty_fig

    df_all = pd.concat(all_frames, ignore_index=True)

    # Self-sufficiency ratio over time
    fig_ratio = px.line(
        df_all,
        x="year",
        y="self_sufficiency_ratio",
        color="country",
        markers=True,
        labels={
            "year": "Year",
            "self_sufficiency_ratio": "Generation / Load",
            "country": "Country",
        },
        title="Self-sufficiency ratio over time",
    )
    fig_ratio.add_hline(
        y=1.0, line_dash="dash", line_color="gray",
        annotation_text="Self-sufficient (ratio=1)",
        annotation_position="top left",
    )

    # Import dependency over time
    fig_import = px.line(
        df_all,
        x="year",
        y="import_dependency",
        color="country",
        markers=True,
        labels={
            "year": "Year",
            "import_dependency": "Net imports / Load",
            "country": "Country",
        },
        title="Import dependency over time",
    )
    fig_import.update_yaxes(tickformat=".0%")
    fig_import.add_hline(y=0, line_dash="dash", line_color="gray")

    # Renewable self-sufficiency over time
    fig_renew = px.line(
        df_all,
        x="year",
        y="renewable_self_sufficiency",
        color="country",
        markers=True,
        labels={
            "year": "Year",
            "renewable_self_sufficiency": "Renewable gen / Load",
            "country": "Country",
        },
        title="Renewable self-sufficiency (renewables / total demand)",
    )
    fig_renew.update_yaxes(tickformat=".0%", range=[0, None])

    # Energy balance stacked bar (first selected country)
    first_country = countries[0]
    df_first = df_all[df_all["country"] == first_country].copy()

    if not df_first.empty:
        fig_balance = go.Figure()

        fig_balance.add_trace(go.Bar(
            x=df_first["year"],
            y=df_first["renewable_generation_gwh"],
            name="Renewable generation",
            marker_color="#4CAF50",
        ))

        # Non-renewable generation
        df_first["non_renewable_gwh"] = (
            df_first["total_generation_gwh"] - df_first["renewable_generation_gwh"]
        )
        fig_balance.add_trace(go.Bar(
            x=df_first["year"],
            y=df_first["non_renewable_gwh"],
            name="Non-renewable generation",
            marker_color="#757575",
        ))

        # Net imports (only positive part)
        df_first["net_import_positive"] = df_first["net_import_gwh"].clip(lower=0)
        fig_balance.add_trace(go.Bar(
            x=df_first["year"],
            y=df_first["net_import_positive"],
            name="Net imports",
            marker_color="#FF7043",
        ))

        # Load line overlay
        fig_balance.add_trace(go.Scatter(
            x=df_first["year"],
            y=df_first["annual_load_gwh"],
            mode="lines+markers",
            name="Total load",
            line=dict(color="#1565C0", width=3),
        ))

        fig_balance.update_layout(
            barmode="stack",
            title=f"Energy balance — {first_country}",
            xaxis_title="Year",
            yaxis_title="GWh",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
    else:
        fig_balance = empty_fig

    return comp_data, comp_columns, fig_ratio, fig_import, fig_renew, fig_balance

@callback(
    Output("ss-detail-table", "data"),
    Output("ss-detail-table", "columns"),
    Input("ss-detail-country", "value"),
    Input("ss-year-range", "value"),
)
def update_detail_table(country, year_range):
    if not country or not year_range:
        return [], []

    start_year, end_year = year_range

    df = get_self_sufficiency(country)
    if df.empty:
        return [], []

    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()

    if df.empty:
        return [], []

    # Format for display
    df_view = pd.DataFrame({
        "year": df["year"].astype(int),
        "generation_gwh": df["total_generation_gwh"].round(1),
        "renewable_gwh": df["renewable_generation_gwh"].round(1),
        "load_gwh": df["annual_load_gwh"].round(1),
        "imports_gwh": df["annual_import_gwh"].round(1),
        "exports_gwh": df["annual_export_gwh"].round(1),
        "net_import_gwh": df["net_import_gwh"].round(1),
        "self_sufficiency": df["self_sufficiency_ratio"].round(3),
        "import_dep_pct": (df["import_dependency"] * 100).round(1),
        "renew_self_suff_pct": (df["renewable_self_sufficiency"] * 100).round(1),
    })

    columns = [
        {"name": "Year", "id": "year"},
        {"name": "Generation (GWh)", "id": "generation_gwh"},
        {"name": "Renewable (GWh)", "id": "renewable_gwh"},
        {"name": "Load (GWh)", "id": "load_gwh"},
        {"name": "Imports (GWh)", "id": "imports_gwh"},
        {"name": "Exports (GWh)", "id": "exports_gwh"},
        {"name": "Net import (GWh)", "id": "net_import_gwh"},
        {"name": "Self-suff. ratio", "id": "self_sufficiency"},
        {"name": "Import dep. (%)", "id": "import_dep_pct"},
        {"name": "Renew. self-suff. (%)", "id": "renew_self_suff_pct"},
    ]

    return df_view.to_dict("records"), columns
