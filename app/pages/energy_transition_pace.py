import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_share,
    get_generation_year_bounds,
    compute_yoy_growth,
    get_transition_scorecard,
    get_tech_growth,
    get_transition_acceleration,
)

dash.register_page(
    __name__,
    path="/energy-transition-pace",
    name="Energy transition pace",
    title="Energy transition pace",
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
        html.H2("Energy Transition Pace"),
        html.P(
            "Measures how fast countries are growing their renewable generation. "
            "Uses Year-over-Year (YoY) growth rates and Compound Annual Growth Rate (CAGR) "
            "to rank countries and compare technology-level progress.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Countries (select for detailed view)"),
                        dcc.Dropdown(
                            id="etp-countries",
                            options=COUNTRY_OPTIONS,
                            value=["PL", "DE", "ES", "FR", "IT"],
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
                            id="etp-year-range",
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

        # Section 1: Transition Scorecard
        html.H3("Transition Scorecard", style={"marginTop": "1rem"}),
        html.P(
            "All countries ranked by their renewable share improvement (percentage points gained). "
            "CAGR measures the smoothed annual growth rate of renewable generation volume.",
            style={"color": "#666", "fontSize": "0.9rem"},
        ),
        dash_table.DataTable(
            id="etp-scorecard-table",
            columns=[],
            data=[],
            page_size=15,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "8px"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f0f0f0"},
            style_data_conditional=[
                {
                    "if": {"filter_query": "{share_change_pp} > 10"},
                    "backgroundColor": "#e8f5e9",
                },
                {
                    "if": {"filter_query": "{share_change_pp} < 0"},
                    "backgroundColor": "#ffebee",
                },
                {
                    "if": {"column_id": "rank", "filter_query": "{rank} <= 3"},
                    "fontWeight": "bold",
                    "color": "#1b5e20",
                },
            ],
        ),

        # Section 2: YoY Growth Chart (selected countries)
        html.H3("Year-over-Year Renewable Generation Growth", style={"marginTop": "2rem"}),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("YoY growth rate (%)"),
                        dcc.Graph(id="etp-yoy-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Renewable share trajectory"),
                        dcc.Graph(id="etp-share-trajectory-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 3: Technology breakdown
        html.H3("Growth by Technology (CAGR %)", style={"marginTop": "2rem"}),
        html.P(
            "Which technologies are driving the transition? Compares compound annual growth "
            "rates of hydro, wind, solar, geothermal, and other renewables.",
            style={"color": "#666", "fontSize": "0.9rem"},
        ),
        dcc.Graph(id="etp-tech-graph"),

        # Section 4: Acceleration indicator
        html.H3("Acceleration vs Deceleration", style={"marginTop": "2rem"}),
        html.P(
            "Is the transition speeding up or slowing down? Compares the average YoY growth "
            "in the first half of the period vs the second half.",
            style={"color": "#666", "fontSize": "0.9rem"},
        ),
        dcc.Graph(id="etp-acceleration-graph"),
    ]
)

# -----------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------

@callback(
    Output("etp-scorecard-table", "data"),
    Output("etp-scorecard-table", "columns"),
    Output("etp-yoy-graph", "figure"),
    Output("etp-share-trajectory-graph", "figure"),
    Output("etp-tech-graph", "figure"),
    Output("etp-acceleration-graph", "figure"),
    Input("etp-countries", "value"),
    Input("etp-year-range", "value"),
)
def update_transition_pace(countries, year_range):
    empty_fig = go.Figure()

    if not countries or not year_range:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    # --- Scorecard (ALL countries, not just selected) ---
    scorecard = get_transition_scorecard(COUNTRIES, start_year, end_year)

    if scorecard.empty:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    scorecard_columns = [
        {"name": "#", "id": "rank"},
        {"name": "Country", "id": "country"},
        {"name": f"Share {start_year} (%)", "id": "start_share_pct"},
        {"name": f"Share {end_year} (%)", "id": "end_share_pct"},
        {"name": "Change (pp)", "id": "share_change_pp"},
        {"name": "CAGR (%)", "id": "cagr_pct"},
        {"name": "Avg YoY (%)", "id": "avg_yoy_growth_pct"},
    ]
    scorecard_data = scorecard.to_dict("records")

    # --- YoY growth chart (selected countries only) ---
    yoy_frames = []
    for country in countries:
        df_yoy = compute_yoy_growth(country, start_year, end_year)
        if df_yoy.empty:
            continue
        df_yoy = df_yoy.dropna(subset=["yoy_growth_pct"])
        df_yoy["country"] = country
        yoy_frames.append(df_yoy)

    if yoy_frames:
        df_yoy_all = pd.concat(yoy_frames, ignore_index=True)

        fig_yoy = px.line(
            df_yoy_all,
            x="year",
            y="yoy_growth_pct",
            color="country",
            markers=True,
            labels={
                "year": "Year",
                "yoy_growth_pct": "YoY growth (%)",
                "country": "Country",
            },
            title="Renewable generation — year-over-year growth",
        )
        fig_yoy.add_hline(y=0, line_dash="dash", line_color="gray")
    else:
        fig_yoy = empty_fig

    # --- Renewable share trajectory (selected countries) ---
    share_frames = []
    for country in countries:
        df_c = get_generation_share(country)
        if df_c.empty:
            continue
        df_c = df_c[(df_c["year"] >= start_year) & (df_c["year"] <= end_year)].copy()
        df_c = df_c.dropna(subset=["renewable_share"])
        df_c["country"] = country
        share_frames.append(df_c)

    if share_frames:
        df_share_all = pd.concat(share_frames, ignore_index=True)

        fig_share = px.line(
            df_share_all,
            x="year",
            y="renewable_share",
            color="country",
            markers=True,
            labels={
                "year": "Year",
                "renewable_share": "Renewable share",
                "country": "Country",
            },
            title="Renewable share of total generation over time",
        )
        fig_share.update_yaxes(tickformat=".0%", range=[0, 1])
    else:
        fig_share = empty_fig

    # --- Technology growth (CAGR by tech, selected countries) ---
    df_tech = get_tech_growth(countries, start_year, end_year)

    if not df_tech.empty:
        df_tech_valid = df_tech.dropna(subset=["cagr_pct"])
        fig_tech = px.bar(
            df_tech_valid,
            x="country",
            y="cagr_pct",
            color="technology",
            barmode="group",
            labels={
                "country": "Country",
                "cagr_pct": "CAGR (%)",
                "technology": "Technology",
            },
            title="Compound Annual Growth Rate by technology",
            color_discrete_map={
                "Hydro": "#2196F3",
                "Wind": "#4CAF50",
                "Solar": "#FFC107",
                "Geothermal": "#FF5722",
                "Other renewables": "#9C27B0",
            },
        )
    else:
        fig_tech = empty_fig

    # --- Acceleration chart (selected countries) ---
    df_accel = get_transition_acceleration(countries, start_year, end_year)

    if not df_accel.empty:
        fig_accel = make_subplots(specs=[[{"secondary_y": False}]])

        fig_accel.add_trace(
            go.Bar(
                x=df_accel["country"],
                y=df_accel["first_half_avg_yoy"],
                name="1st half avg YoY",
                marker_color="#90CAF9",
            )
        )
        fig_accel.add_trace(
            go.Bar(
                x=df_accel["country"],
                y=df_accel["second_half_avg_yoy"],
                name="2nd half avg YoY",
                marker_color="#1565C0",
            )
        )
        fig_accel.add_trace(
            go.Scatter(
                x=df_accel["country"],
                y=df_accel["acceleration"],
                mode="markers+text",
                name="Acceleration (pp)",
                marker=dict(
                    size=14,
                    color=df_accel["acceleration"].apply(
                        lambda v: "#4CAF50" if v > 0 else "#F44336"
                    ),
                    symbol="diamond",
                ),
                text=df_accel["acceleration"].apply(lambda v: f"{v:+.1f}"),
                textposition="top center",
            )
        )

        fig_accel.update_layout(
            barmode="group",
            title="Is the transition accelerating? (2nd half vs 1st half of period)",
            xaxis_title="Country",
            yaxis_title="Avg YoY growth (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
    else:
        fig_accel = empty_fig

    return scorecard_data, scorecard_columns, fig_yoy, fig_share, fig_tech, fig_accel
