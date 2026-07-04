import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_year_bounds,
    get_renewable_share_comparison,
    get_technology_mix_comparison,
    get_renewable_growth_comparison,
    get_renewable_gap_to_target,
)

dash.register_page(
    __name__,
    path="/compare-renewables",
    name="Compare renewables",
    title="Compare renewables",
)

_eu_df = load_eurostat_share_annual()
COUNTRIES = sorted(_eu_df["country"].unique())
COUNTRY_OPTIONS = [{"label": c, "value": c} for c in COUNTRIES]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div(
    [
        html.H2("Compare Renewable Generation"),
        html.P(
            "Multi-country comparison of renewable energy progress — share trajectories, "
            "technology mixes, growth rates, and distance to targets.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Countries"),
                        dcc.Dropdown(
                            id="cr-countries",
                            options=COUNTRY_OPTIONS,
                            value=["DE", "PL", "ES", "FR", "SE"],
                            multi=True,
                            clearable=False,
                        ),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Year range"),
                        dcc.RangeSlider(
                            id="cr-year-range",
                            min=MIN_YEAR,
                            max=MAX_YEAR,
                            value=[MIN_YEAR, MAX_YEAR],
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                            allowCross=False,
                        ),
                    ],
                    style={"width": "45%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        # Section 1: Share trajectories
        html.H3("Renewable Share Trajectories"),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Graph(id="cr-share-graph"),
                    ],
                    style={"width": "55%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Growth Summary"),
                        dash_table.DataTable(
                            id="cr-growth-table",
                            columns=[],
                            data=[],
                            sort_action="native",
                            style_table={"overflowX": "auto"},
                            style_cell={"textAlign": "center", "padding": "6px", "fontSize": "0.85rem"},
                            style_header={"fontWeight": "bold", "backgroundColor": "#f0f0f0"},
                            style_data_conditional=[
                                {"if": {"filter_query": "{share_gain_pp} > 15"}, "backgroundColor": "#e8f5e9"},
                                {"if": {"filter_query": "{share_gain_pp} < 0"}, "backgroundColor": "#ffebee"},
                            ],
                        ),
                    ],
                    style={"width": "45%", "display": "inline-block", "verticalAlign": "top"},
                ),
            ],
        ),

        # Section 2: Technology mix (latest year)
        html.H3("Technology Mix (latest year)", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Renewable generation by technology (GWh)"),
                        dcc.Graph(id="cr-tech-abs-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Technology share within renewables (%)"),
                        dcc.Graph(id="cr-tech-pct-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 3: Growth race
        html.H3("Growth Race", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Absolute renewable generation growth (GWh)"),
                        dcc.Graph(id="cr-growth-abs-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("CAGR comparison (%)"),
                        dcc.Graph(id="cr-cagr-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 4: Gap to target
        html.H3("Gap to Target", style={"marginTop": "2rem"}),
        html.P(
            "How far is each country from a 50% renewable share? "
            "Shows additional generation (GWh) needed to reach the target.",
            style={"color": "#666", "fontSize": "0.9rem"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Target renewable share (%)"),
                        dcc.Slider(
                            id="cr-target-slider",
                            min=30,
                            max=100,
                            value=50,
                            marks={i: f"{i}%" for i in range(30, 101, 10)},
                            step=5,
                        ),
                    ],
                    style={"width": "50%", "marginBottom": "1rem"},
                ),
            ],
        ),
        dcc.Graph(id="cr-gap-graph"),
    ]
)

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

@callback(
    Output("cr-share-graph", "figure"),
    Output("cr-growth-table", "data"),
    Output("cr-growth-table", "columns"),
    Output("cr-tech-abs-graph", "figure"),
    Output("cr-tech-pct-graph", "figure"),
    Output("cr-growth-abs-graph", "figure"),
    Output("cr-cagr-graph", "figure"),
    Output("cr-gap-graph", "figure"),
    Input("cr-countries", "value"),
    Input("cr-year-range", "value"),
    Input("cr-target-slider", "value"),
)
def update_compare_renewables(countries, year_range, target_pct):
    empty_fig = go.Figure()

    if not countries or not year_range:
        return empty_fig, [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    # --- Section 1: Share trajectories ---
    df_share = get_renewable_share_comparison(countries, start_year, end_year)

    if df_share.empty:
        return empty_fig, [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    fig_share = px.line(
        df_share,
        x="year",
        y="renewable_share",
        color="country",
        markers=True,
        labels={
            "year": "Year",
            "renewable_share": "Renewable share",
            "country": "Country",
        },
        title="Renewable share of generation",
    )
    fig_share.update_yaxes(tickformat=".0%", range=[0, 1])

    # Add EU average reference if enough countries
    if len(countries) >= 3:
        avg_by_year = df_share.groupby("year")["renewable_share"].mean().reset_index()
        fig_share.add_trace(go.Scatter(
            x=avg_by_year["year"],
            y=avg_by_year["renewable_share"],
            mode="lines",
            name="Selection average",
            line=dict(color="black", width=2, dash="dot"),
        ))

    # Growth summary table
    df_growth = get_renewable_growth_comparison(countries, start_year, end_year)

    if df_growth.empty:
        growth_data = []
        growth_cols = []
    else:
        df_growth_sorted = df_growth.sort_values("share_gain_pp", ascending=False)
        growth_cols = [
            {"name": "Country", "id": "country"},
            {"name": f"Share {start_year} (%)", "id": "share_start_pct"},
            {"name": f"Share {end_year} (%)", "id": "share_end_pct"},
            {"name": "Gain (pp)", "id": "share_gain_pp"},
            {"name": "Growth (%)", "id": "growth_pct"},
            {"name": "CAGR (%)", "id": "cagr_pct"},
        ]
        growth_data = df_growth_sorted.to_dict("records")

    # --- Section 2: Technology mix (latest year) ---
    df_tech = get_technology_mix_comparison(countries, end_year)

    if df_tech.empty:
        fig_tech_abs = empty_fig
        fig_tech_pct = empty_fig
    else:
        # Absolute generation by technology
        fig_tech_abs = px.bar(
            df_tech,
            x="country",
            y="generation_gwh",
            color="fuel",
            labels={"country": "Country", "generation_gwh": "Generation (GWh)", "fuel": "Technology"},
            title=f"Renewable generation by technology — {end_year}",
            color_discrete_map={
                "Hydro": "#2196F3",
                "Wind": "#4CAF50",
                "Solar": "#FFC107",
                "Geothermal": "#FF5722",
                "Other renewables": "#9C27B0",
            },
        )

        # Percentage within renewables (stacked to 100%)
        fig_tech_pct = px.bar(
            df_tech,
            x="country",
            y="share_of_renewable",
            color="fuel",
            labels={"country": "Country", "share_of_renewable": "% of renewables", "fuel": "Technology"},
            title=f"Technology mix within renewables — {end_year}",
            color_discrete_map={
                "Hydro": "#2196F3",
                "Wind": "#4CAF50",
                "Solar": "#FFC107",
                "Geothermal": "#FF5722",
                "Other renewables": "#9C27B0",
            },
        )
        fig_tech_pct.update_layout(barmode="stack")
        fig_tech_pct.update_yaxes(range=[0, 100])

    # --- Section 3: Growth race ---
    if df_growth.empty:
        fig_growth_abs = empty_fig
        fig_cagr = empty_fig
    else:
        # Absolute growth (waterfall-style bar)
        df_growth_sorted2 = df_growth.sort_values("absolute_growth_gwh", ascending=False)

        fig_growth_abs = go.Figure()
        fig_growth_abs.add_trace(go.Bar(
            x=df_growth_sorted2["country"],
            y=df_growth_sorted2["absolute_growth_gwh"],
            marker_color=df_growth_sorted2["absolute_growth_gwh"].apply(
                lambda v: "#4CAF50" if v > 0 else "#F44336"
            ),
            text=df_growth_sorted2["absolute_growth_gwh"].apply(lambda v: f"{v:+,.0f}"),
            textposition="outside",
        ))
        fig_growth_abs.update_layout(
            title=f"Renewable generation added ({start_year}→{end_year})",
            xaxis_title="Country",
            yaxis_title="Growth (GWh)",
            showlegend=False,
        )

        # CAGR comparison
        df_cagr = df_growth.dropna(subset=["cagr_pct"]).sort_values("cagr_pct", ascending=False)

        fig_cagr = go.Figure()
        fig_cagr.add_trace(go.Bar(
            x=df_cagr["country"],
            y=df_cagr["cagr_pct"],
            marker_color=df_cagr["cagr_pct"].apply(
                lambda v: "#4CAF50" if v > 3 else ("#FFC107" if v > 0 else "#F44336")
            ),
            text=df_cagr["cagr_pct"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
        ))
        fig_cagr.update_layout(
            title=f"Compound Annual Growth Rate ({start_year}→{end_year})",
            xaxis_title="Country",
            yaxis_title="CAGR (%)",
            showlegend=False,
        )

    # --- Section 4: Gap to target ---
    df_gap = get_renewable_gap_to_target(countries, end_year, target_pct)

    if df_gap.empty:
        fig_gap = empty_fig
    else:
        df_gap_sorted = df_gap.sort_values("gap_pp", ascending=True)

        fig_gap = go.Figure()

        # Current share as bars
        fig_gap.add_trace(go.Bar(
            x=df_gap_sorted["country"],
            y=df_gap_sorted["current_share_pct"],
            name="Current share (%)",
            marker_color=df_gap_sorted["status"].apply(
                lambda s: "#4CAF50" if s == "Above target" else ("#FFC107" if s == "Close" else "#FF7043")
            ),
        ))

        # Target line
        fig_gap.add_hline(
            y=target_pct,
            line_dash="dash",
            line_color="#F44336",
            annotation_text=f"Target: {target_pct}%",
            annotation_position="top right",
        )

        # Add gap annotations
        for _, row in df_gap_sorted.iterrows():
            if row["gap_pp"] > 0:
                fig_gap.add_annotation(
                    x=row["country"],
                    y=row["current_share_pct"] + 2,
                    text=f"−{row['gap_pp']:.0f}pp<br>({row['additional_gwh_needed']:,.0f} GWh needed)",
                    showarrow=False,
                    font=dict(size=9, color="#D32F2F"),
                )

        fig_gap.update_layout(
            title=f"Distance to {target_pct}% renewable target — {end_year}",
            xaxis_title="Country",
            yaxis_title="Renewable share (%)",
            yaxis=dict(range=[0, max(target_pct + 20, df_gap_sorted["current_share_pct"].max() + 15)]),
            showlegend=False,
        )

    return (
        fig_share, growth_data, growth_cols,
        fig_tech_abs, fig_tech_pct,
        fig_growth_abs, fig_cagr, fig_gap
    )
