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
    get_renewables_vs_load_detail,
    get_renewables_load_kpis,
    get_generation_by_fuel,
)

dash.register_page(
    __name__,
    path="/renewables-vs-load",
    name="Renewables vs load",
    title="Renewables vs load",
)

# Eurostat annual data drives country list and year bounds
_eu_df = load_eurostat_share_annual()
COUNTRY_OPTIONS = [{"label": c, "value": c} for c in sorted(_eu_df["country"].unique())]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div(
    [
        html.H2("Renewables vs Demand"),
        html.P(
            "How much of a country's electricity demand is met by renewables? "
            "Tracks the gap between renewable generation and total load, showing "
            "whether the energy transition is actually displacing fossil fuels.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="rvl-country",
                            options=COUNTRY_OPTIONS,
                            value="DE",
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Year range"),
                        dcc.RangeSlider(
                            id="rvl-year-range",
                            min=MIN_YEAR,
                            max=MAX_YEAR,
                            value=[MIN_YEAR, MAX_YEAR],
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                            allowCross=False,
                        ),
                    ],
                    style={"width": "65%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "1.5rem"},
        ),

        # KPI cards
        html.Div(id="rvl-kpis", style={"marginBottom": "2rem"}),

        # Row 1: Energy balance stacked area + Renewable coverage line
        html.Div(
            [
                html.Div(
                    [
                        html.H4("How is demand met? (stacked supply)"),
                        dcc.Graph(id="rvl-balance-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Renewable coverage of demand (%)"),
                        dcc.Graph(id="rvl-coverage-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Row 2: Generation vs Load dual-axis + Fossil displacement
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Generation vs Load"),
                        dcc.Graph(id="rvl-genload-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Fossil dependency (% of load)"),
                        dcc.Graph(id="rvl-fossil-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
            style={"marginTop": "1rem"},
        ),

        # Row 3: Technology contribution to covering demand
        html.H4("Which renewables are closing the gap?", style={"marginTop": "2rem"}),
        dcc.Graph(id="rvl-tech-graph"),

        # Detail table (collapsed, secondary)
        html.Details(
            [
                html.Summary("Show detailed data table", style={"cursor": "pointer", "marginTop": "2rem", "fontWeight": "bold"}),
                dash_table.DataTable(
                    id="rvl-table",
                    columns=[],
                    data=[],
                    page_size=12,
                    sort_action="native",
                    style_table={"overflowX": "auto", "marginTop": "1rem"},
                    style_cell={"textAlign": "center", "padding": "6px", "fontSize": "0.85rem"},
                    style_header={"fontWeight": "bold", "backgroundColor": "#f0f0f0"},
                ),
            ],
        ),
    ]
)

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

    start_year, end_year = year_range

    df = get_renewables_vs_load_detail(country, start_year, end_year)
    kpis = get_renewables_load_kpis(country, start_year, end_year)

    if df.empty or not kpis:
        return html.Div("No data available.", style={"color": "red"}), empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, [], []

    # --- KPI cards ---
    ren_growth_color = "#4CAF50" if kpis["renewable_change_pct"] > 0 else "#F44336"
    fossil_color = "#4CAF50" if kpis["fossil_displacement_pp"] > 0 else "#F44336"
    load_color = "#FF9800" if abs(kpis["load_change_pct"]) > 5 else "#666"

    kpi_children = html.Div(
        style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"},
        children=[
            _kpi_card(
                "Renewable Coverage",
                f"{kpis['renewable_coverage_pct']:.1f}%",
                f"{kpis['coverage_change_pp']:+.1f} pp over period",
                value_color="#4CAF50",
            ),
            _kpi_card(
                "Renewable Growth",
                f"{kpis['renewable_change_pct']:+.1f}%",
                f"{kpis['latest_renewable_gwh']:,.0f} GWh ({kpis['latest_year']})",
                value_color=ren_growth_color,
            ),
            _kpi_card(
                "Load Change",
                f"{kpis['load_change_pct']:+.1f}%",
                f"{kpis['latest_load_gwh']:,.0f} GWh ({kpis['latest_year']})",
                value_color=load_color,
            ),
            _kpi_card(
                "Fossil Displaced",
                f"{kpis['fossil_displacement_pp']:+.1f} pp",
                "reduction in fossil share of demand",
                value_color=fossil_color,
            ),
            _kpi_card(
                "Generation Surplus",
                f"{kpis['latest_surplus_gwh']:+,.0f} GWh",
                "+ = generates more than it consumes",
                value_color="#1565C0" if kpis["latest_surplus_gwh"] > 0 else "#E65100",
            ),
        ],
    )

    # --- Chart 1: Stacked supply balance ---
    fig_balance = go.Figure()

    fig_balance.add_trace(go.Bar(
        x=df["year"],
        y=df["renewable_generation_gwh"],
        name="Renewable generation",
        marker_color="#4CAF50",
    ))

    fig_balance.add_trace(go.Bar(
        x=df["year"],
        y=df["non_renewable_gwh"],
        name="Non-renewable generation",
        marker_color="#757575",
    ))

    # Load line overlay
    fig_balance.add_trace(go.Scatter(
        x=df["year"],
        y=df["annual_load_gwh"],
        mode="lines+markers",
        name="Total demand",
        line=dict(color="#1565C0", width=3),
        marker=dict(size=6),
    ))

    fig_balance.update_layout(
        barmode="stack",
        title=f"Supply vs demand — {country}",
        xaxis_title="Year",
        yaxis_title="GWh",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # --- Chart 2: Renewable coverage % over time ---
    fig_coverage = go.Figure()

    fig_coverage.add_trace(go.Scatter(
        x=df["year"],
        y=df["renewable_coverage_pct"],
        mode="lines+markers",
        fill="tozeroy",
        name="Renewable coverage",
        line=dict(color="#4CAF50", width=2.5),
        fillcolor="rgba(76,175,80,0.15)",
    ))

    # Add 100% target line
    fig_coverage.add_hline(
        y=100, line_dash="dash", line_color="#F44336",
        annotation_text="100% coverage",
        annotation_position="top right",
    )

    # Add 50% reference
    fig_coverage.add_hline(
        y=50, line_dash="dot", line_color="#999",
        annotation_text="50%",
        annotation_position="bottom right",
    )

    fig_coverage.update_layout(
        title=f"Renewable coverage of demand — {country}",
        xaxis_title="Year",
        yaxis_title="% of demand met by renewables",
        yaxis=dict(range=[0, max(df["renewable_coverage_pct"].max() * 1.15, 105)]),
        showlegend=False,
    )

    # --- Chart 3: Generation vs Load (dual axis) ---
    fig_genload = make_subplots(specs=[[{"secondary_y": True}]])

    fig_genload.add_trace(
        go.Bar(
            x=df["year"],
            y=df["total_generation_gwh"],
            name="Total generation",
            marker_color="#42A5F5",
            opacity=0.7,
        ),
        secondary_y=False,
    )

    fig_genload.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["annual_load_gwh"],
            mode="lines+markers",
            name="Total load",
            line=dict(color="#E65100", width=2.5),
        ),
        secondary_y=False,
    )

    # Surplus/deficit as secondary
    fig_genload.add_trace(
        go.Bar(
            x=df["year"],
            y=df["generation_surplus_gwh"],
            name="Surplus (+) / Deficit (−)",
            marker_color=df["generation_surplus_gwh"].apply(
                lambda v: "rgba(76,175,80,0.6)" if v >= 0 else "rgba(244,67,54,0.6)"
            ),
        ),
        secondary_y=True,
    )

    fig_genload.update_layout(
        title=f"Generation vs Load — {country}",
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_genload.update_yaxes(title_text="GWh", secondary_y=False)
    fig_genload.update_yaxes(title_text="Surplus / deficit (GWh)", secondary_y=True)

    # --- Chart 4: Fossil dependency declining ---
    fig_fossil = go.Figure()

    fig_fossil.add_trace(go.Scatter(
        x=df["year"],
        y=df["fossil_dependency_pct"],
        mode="lines+markers",
        fill="tozeroy",
        name="Fossil dependency",
        line=dict(color="#F44336", width=2.5),
        fillcolor="rgba(244,67,54,0.1)",
    ))

    fig_fossil.add_hline(y=0, line_dash="dash", line_color="gray")

    fig_fossil.update_layout(
        title=f"Fossil dependency (non-renewable gen / load) — {country}",
        xaxis_title="Year",
        yaxis_title="% of demand met by fossil/nuclear",
        yaxis=dict(range=[0, None]),
        showlegend=False,
    )

    # --- Chart 5: Technology contribution stacked area ---
    df_fuel = get_generation_by_fuel(country)

    if df_fuel.empty:
        fig_tech = empty_fig
    else:
        df_fuel = df_fuel[(df_fuel["year"] >= start_year) & (df_fuel["year"] <= end_year)].copy()

        # Convert to % of load
        load_by_year = df[["year", "annual_load_gwh"]].set_index("year")["annual_load_gwh"]
        df_fuel = df_fuel.merge(
            df[["year", "annual_load_gwh"]], on="year", how="left"
        )
        df_fuel["pct_of_load"] = (df_fuel["generation_gwh"] / df_fuel["annual_load_gwh"]) * 100

        fig_tech = px.area(
            df_fuel,
            x="year",
            y="pct_of_load",
            color="fuel",
            labels={
                "year": "Year",
                "pct_of_load": "% of demand covered",
                "fuel": "Technology",
            },
            title=f"Renewable contribution to demand by technology — {country}",
            color_discrete_map={
                "Hydro total": "#2196F3",
                "Wind total": "#4CAF50",
                "Solar total": "#FFC107",
                "Geothermal": "#FF5722",
                "Other renewables": "#9C27B0",
                "Renewables & biofuels (aggregate)": "#009688",
            },
        )
        fig_tech.update_yaxes(title_text="% of total demand")

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

    # Round for display
    for col in df_view.columns:
        if col != "year":
            df_view[col] = df_view[col].round(1)

    table_columns = [
        {"name": "Year", "id": "year"},
        {"name": "Generation (GWh)", "id": "generation_gwh"},
        {"name": "Renewable (GWh)", "id": "renewable_gwh"},
        {"name": "Non-renew. (GWh)", "id": "non_renewable_gwh"},
        {"name": "Load (GWh)", "id": "load_gwh"},
        {"name": "Renew. coverage (%)", "id": "renewable_coverage_pct"},
        {"name": "Fossil dep. (%)", "id": "fossil_dep_pct"},
        {"name": "Surplus (GWh)", "id": "surplus_gwh"},
    ]

    return (
        kpi_children, fig_balance, fig_coverage, fig_genload,
        fig_fossil, fig_tech, df_view.to_dict("records"), table_columns
    )

# --- Helper ---

def _kpi_card(title: str, value: str, subtitle: str, value_color: str = "#212121"):
    return html.Div(
        [
            html.Div(title, style={"fontSize": "0.8rem", "color": "#666", "marginBottom": "4px"}),
            html.Div(value, style={"fontSize": "1.4rem", "fontWeight": "bold", "color": value_color}),
            html.Div(subtitle, style={"fontSize": "0.7rem", "color": "#999", "marginTop": "2px"}),
        ],
        style={
            "flex": "1",
            "minWidth": "140px",
            "padding": "0.8rem",
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
            "textAlign": "center",
            "backgroundColor": "#fafafa",
        },
    )
