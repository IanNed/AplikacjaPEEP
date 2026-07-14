import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_year_bounds,
    get_renewables_vs_load_detail,
    get_renewables_load_kpis,
    get_generation_by_fuel,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card, kpi_card, kpi_row,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/renewables-vs-load",
    name="OZE vs obciążenie",
    title="OZE vs obciążenie",
)

# Eurostat annual data drives country list and year bounds
_eu_df = load_eurostat_share_annual()
COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_eu_df["country"].unique())
]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "OZE vs zapotrzebowanie",
        "Jaka część zapotrzebowania na energię elektryczną jest pokrywana przez OZE? "
        "Śledzi lukę między generacją odnawialną a całkowitym obciążeniem, pokazując "
        "czy transformacja energetyczna rzeczywiście wypiera paliwa kopalne."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraj", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="rvl-country",
                    options=COUNTRY_OPTIONS,
                    value="PL",
                    clearable=False,
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Zakres lat", style={"color": "#ccc"}),
                dcc.RangeSlider(
                    id="rvl-year-range",
                    min=MIN_YEAR,
                    max=MAX_YEAR,
                    value=[MIN_YEAR, MAX_YEAR],
                    marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                    allowCross=False,
                ),
            ], md=8),
        ]),
    ),

    # KPI cards
    html.Div(id="rvl-kpis", className="mb-4"),

    # Row 1: Energy balance + Renewable coverage
    dbc.Row([
        dbc.Col(chart_card("Jak pokrywane jest zapotrzebowanie?", "rvl-balance-graph"), md=6),
        dbc.Col(chart_card("Pokrycie zapotrzebowania przez OZE (%)", "rvl-coverage-graph"), md=6),
    ]),

    # Row 2: Generation vs Load + Fossil displacement
    dbc.Row([
        dbc.Col(chart_card("Generacja vs obciążenie", "rvl-genload-graph"), md=6),
        dbc.Col(chart_card("Zależność od paliw kopalnych (% obciążenia)", "rvl-fossil-graph"), md=6),
    ]),

    # Row 3: Technology contribution
    section_header(
        "Które OZE domykają lukę?",
        "Wykres warstwowy pokazujący wkład każdej technologii jako % całkowitego zapotrzebowania."
    ),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="rvl-tech-graph", style={"height": "400px"}),
            style={"padding": "0.5rem"},
        ),
        className="mb-4",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),

    # Detail table (collapsible)
    section_header("Szczegółowe dane roczne"),
    html.Details([
        html.Summary("Pokaż tabelę danych", style={
            "cursor": "pointer", "fontWeight": "bold", "color": "#ccc", "marginBottom": "1rem"
        }),
        dash_table.DataTable(
            id="rvl-table",
            columns=[],
            data=[],
            page_size=12,
            sort_action="native",
            **DARK_TABLE_STYLE,
        ),
    ]),
])

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

@callback(
    Output("rvl-kpis", "children"),
    Output("rvl-balance-graph", "figure"),
    Output("rvl-coverage-graph", "figure"),
    Output("rvl-genload-graph", "figure"),
    Output("rvl-fossil-graph", "figure"),
    Output("rvl-tech-graph", "figure"),
    Output("rvl-table", "data"),
    Output("rvl-table", "columns"),
    Input("rvl-country", "value"),
    Input("rvl-year-range", "value"),
)
def update_renewables_vs_load(country, year_range):
    empty_fig = go.Figure()

    if not country or not year_range:
        return html.Div(), empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, [], []

    country_name = COUNTRY_NAMES_PL.get(country, country)
    start_year, end_year = year_range

    df = get_renewables_vs_load_detail(country, start_year, end_year)
    kpis = get_renewables_load_kpis(country, start_year, end_year)

    if df.empty or not kpis:
        msg = html.Div("Brak dostępnych danych.", style={"color": "#ff6b6b", "padding": "1rem"})
        return msg, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, [], []

    # --- KPI cards ---
    ren_growth_color = "#00d4aa" if kpis["renewable_change_pct"] > 0 else "#ff6b6b"
    fossil_color = "#00d4aa" if kpis["fossil_displacement_pp"] > 0 else "#ff6b6b"
    load_color = "#ffd93d" if abs(kpis["load_change_pct"]) > 5 else "#e0e0e0"
    surplus_color = "#3391ff" if kpis["latest_surplus_gwh"] > 0 else "#f97316"

    kpi_children = kpi_row([
        kpi_card(
            "Pokrycie OZE",
            f"{kpis['renewable_coverage_pct']:.1f}%",
            f"{kpis['coverage_change_pp']:+.1f} pp w okresie",
            value_color="#00d4aa",
        ),
        kpi_card(
            "Wzrost OZE",
            f"{kpis['renewable_change_pct']:+.1f}%",
            f"{kpis['latest_renewable_gwh']:,.0f} GWh ({kpis['latest_year']})",
            value_color=ren_growth_color,
        ),
        kpi_card(
            "Zmiana obciążenia",
            f"{kpis['load_change_pct']:+.1f}%",
            f"{kpis['latest_load_gwh']:,.0f} GWh ({kpis['latest_year']})",
            value_color=load_color,
        ),
        kpi_card(
            "Wyparte paliwa kop.",
            f"{kpis['fossil_displacement_pp']:+.1f} pp",
            "redukcja udziału fossil w zapotrzebowaniu",
            value_color=fossil_color,
        ),
        kpi_card(
            "Nadwyżka generacji",
            f"{kpis['latest_surplus_gwh']:+,.0f} GWh",
            "+ = generuje więcej niż zużywa",
            value_color=surplus_color,
        ),
    ])

    # --- Chart 1: Stacked supply balance ---
    fig_balance = go.Figure()

    fig_balance.add_trace(go.Bar(
        x=df["year"],
        y=df["renewable_generation_gwh"],
        name="Generacja OZE",
        marker_color="#00d4aa",
    ))

    fig_balance.add_trace(go.Bar(
        x=df["year"],
        y=df["non_renewable_gwh"],
        name="Generacja nie-OZE",
        marker_color="#555",
    ))

    fig_balance.add_trace(go.Scatter(
        x=df["year"],
        y=df["annual_load_gwh"],
        mode="lines+markers",
        name="Zapotrzebowanie całkowite",
        line=dict(color="#3391ff", width=3),
        marker=dict(size=6),
    ))

    fig_balance.update_layout(
        barmode="stack",
        title=f"Podaż vs zapotrzebowanie — {country_name}",
        xaxis_title="Rok",
        yaxis_title="GWh",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # --- Chart 2: Renewable coverage % ---
    fig_coverage = go.Figure()

    fig_coverage.add_trace(go.Scatter(
        x=df["year"],
        y=df["renewable_coverage_pct"],
        mode="lines+markers",
        fill="tozeroy",
        name="Pokrycie OZE",
        line=dict(color="#00d4aa", width=2.5),
        fillcolor="rgba(0,212,170,0.12)",
    ))

    fig_coverage.add_hline(
        y=100, line_dash="dash", line_color="#ff6b6b",
        annotation_text="100% pokrycia",
        annotation_position="top right",
        annotation_font_color="#ff6b6b",
    )
    fig_coverage.add_hline(
        y=50, line_dash="dot", line_color="rgba(255,255,255,0.3)",
        annotation_text="50%",
        annotation_position="bottom right",
        annotation_font_color="#999",
    )

    fig_coverage.update_layout(
        title=f"Pokrycie zapotrzebowania przez OZE — {country_name}",
        xaxis_title="Rok",
        yaxis_title="% zapotrzebowania pokrytego przez OZE",
        yaxis=dict(range=[0, max(df["renewable_coverage_pct"].max() * 1.15, 105)]),
        showlegend=False,
    )

    # --- Chart 3: Generation vs Load (dual axis) ---
    fig_genload = make_subplots(specs=[[{"secondary_y": True}]])

    fig_genload.add_trace(
        go.Bar(
            x=df["year"],
            y=df["total_generation_gwh"],
            name="Generacja całkowita",
            marker_color="#3391ff",
            opacity=0.7,
        ),
        secondary_y=False,
    )

    fig_genload.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["annual_load_gwh"],
            mode="lines+markers",
            name="Obciążenie całkowite",
            line=dict(color="#f97316", width=2.5),
        ),
        secondary_y=False,
    )

    fig_genload.add_trace(
        go.Bar(
            x=df["year"],
            y=df["generation_surplus_gwh"],
            name="Nadwyżka (+) / Deficyt (−)",
            marker_color=df["generation_surplus_gwh"].apply(
                lambda v: "rgba(0,212,170,0.5)" if v >= 0 else "rgba(255,107,107,0.5)"
            ),
        ),
        secondary_y=True,
    )

    fig_genload.update_layout(
        title=f"Generacja vs obciążenie — {country_name}",
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_genload.update_yaxes(title_text="GWh", secondary_y=False)
    fig_genload.update_yaxes(title_text="Nadwyżka / deficyt (GWh)", secondary_y=True)

    # --- Chart 4: Fossil dependency declining ---
    fig_fossil = go.Figure()

    fig_fossil.add_trace(go.Scatter(
        x=df["year"],
        y=df["fossil_dependency_pct"],
        mode="lines+markers",
        fill="tozeroy",
        name="Zależność od fossil",
        line=dict(color="#ff6b6b", width=2.5),
        fillcolor="rgba(255,107,107,0.08)",
    ))

    fig_fossil.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")

    fig_fossil.update_layout(
        title=f"Zależność od paliw kopalnych — {country_name}",
        xaxis_title="Rok",
        yaxis_title="% zapotrzebowania pokrytego przez fossil/atom",
        yaxis=dict(range=[0, None]),
        showlegend=False,
    )

    # --- Chart 5: Technology contribution stacked area ---
    df_fuel = get_generation_by_fuel(country)

    if df_fuel.empty:
        fig_tech = empty_fig
    else:
        df_fuel = df_fuel[(df_fuel["year"] >= start_year) & (df_fuel["year"] <= end_year)].copy()

        df_fuel = df_fuel.merge(
            df[["year", "annual_load_gwh"]], on="year", how="left"
        )
        df_fuel["pct_of_load"] = (df_fuel["generation_gwh"] / df_fuel["annual_load_gwh"]) * 100

        # Map fuel names to Polish
        fuel_map_pl = {
            "Hydro total": "Hydro",
            "Wind total": "Wiatr",
            "Solar total": "Słońce",
            "Geothermal": "Geotermia",
            "Other renewables": "Inne OZE",
            "Renewables & biofuels (aggregate)": "OZE i biopaliwa (łącznie)",
        }
        df_fuel["fuel_pl"] = df_fuel["fuel"].map(fuel_map_pl).fillna(df_fuel["fuel"])

        fig_tech = px.area(
            df_fuel,
            x="year",
            y="pct_of_load",
            color="fuel_pl",
            labels={
                "year": "Rok",
                "pct_of_load": "% pokrytego zapotrzebowania",
                "fuel_pl": "Technologia",
            },
            title=f"Wkład OZE w zapotrzebowanie wg technologii — {country_name}",
            color_discrete_map={
                "Hydro": "#06b6d4",
                "Wiatr": "#6bcf7f",
                "Słońce": "#ffd93d",
                "Geotermia": "#f97316",
                "Inne OZE": "#a78bfa",
                "OZE i biopaliwa (łącznie)": "#00d4aa",
            },
        )
        fig_tech.update_yaxes(title_text="% całkowitego zapotrzebowania")

    # --- Detail table ---
    df_view = df[[
        "year", "total_generation_gwh", "renewable_generation_gwh",
        "non_renewable_gwh", "annual_load_gwh", "renewable_coverage_pct",
        "fossil_dependency_pct", "generation_surplus_gwh",
    ]].copy()

    df_view.columns = [
        "year", "generation_gwh", "renewable_gwh", "non_renewable_gwh",
        "load_gwh", "renewable_coverage_pct", "fossil_dep_pct", "surplus_gwh",
    ]

    for col in df_view.columns:
        if col != "year":
            df_view[col] = df_view[col].round(1)

    table_columns = [
        {"name": "Rok", "id": "year"},
        {"name": "Generacja (GWh)", "id": "generation_gwh"},
        {"name": "OZE (GWh)", "id": "renewable_gwh"},
        {"name": "Nie-OZE (GWh)", "id": "non_renewable_gwh"},
        {"name": "Obciążenie (GWh)", "id": "load_gwh"},
        {"name": "Pokrycie OZE (%)", "id": "renewable_coverage_pct"},
        {"name": "Zależność fossil (%)", "id": "fossil_dep_pct"},
        {"name": "Nadwyżka (GWh)", "id": "surplus_gwh"},
    ]

    return (
        kpi_children, fig_balance, fig_coverage, fig_genload,
        fig_fossil, fig_tech, df_view.to_dict("records"), table_columns
    )
