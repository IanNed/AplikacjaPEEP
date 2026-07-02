import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_share,
    get_generation_by_fuel,
    get_generation_year_bounds,
)

dash.register_page(
    __name__,
    path="/renewables-capacity",
    name="Renewables capacity",
    title="Renewables capacity",
)

# Eurostat annual generation share dataset:
# country, year, renewable_generation_gwh, total_generation_gwh, renewable_share
_eu_df = load_eurostat_share_annual()
COUNTRY_OPTIONS = [{"label": c, "value": c} for c in sorted(_eu_df["country"].unique())]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

layout = html.Div(
    [
        html.H2("Renewable generation over time (Eurostat)"),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="rc-country",
                            options=COUNTRY_OPTIONS,
                            value="PL",  # pick your favourite default
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Year range"),
                        dcc.RangeSlider(
                            id="rc-year-range",
                            min=MIN_YEAR,
                            max=MAX_YEAR,
                            value=[MIN_YEAR, MAX_YEAR],
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1, 2)},
                            allowCross=False,
                        ),
                    ],
                    style={"width": "65%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Renewable vs total generation"),
                        dcc.Graph(id="rc-share-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Renewables by fuel (generation)"),
                        dcc.Graph(id="rc-tech-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),
    ]
)


@callback(
    Output("rc-share-graph", "figure"),
    Output("rc-tech-graph", "figure"),
    Input("rc-country", "value"),
    Input("rc-year-range", "value"),
)
def update_renewables_generation(country, year_range):
    if not country or not year_range:
        return px.Figure(), px.Figure()

    start_year, end_year = year_range

    # Annual renewable share and volumes from Eurostat (aggregated)
    df_share = get_generation_share(country)  # year, renewable_generation_gwh, total_generation_gwh, renewable_share
    df_share = df_share[(df_share["year"] >= start_year) & (df_share["year"] <= end_year)].copy()

    if df_share.empty:
        return px.Figure(), px.Figure()

    # Chart 1: renewable generation and share over time (bar + line)
    fig_share_bar = px.bar(
        df_share,
        x="year",
        y="renewable_generation_gwh",
        labels={
            "year": "Year",
            "renewable_generation_gwh": "Renewable generation (GWh)",
        },
        title=f"Renewable generation and share in {country}",
    )

    fig_share_line = px.line(
        df_share,
        x="year",
        y="renewable_share",
    )
    fig_share_line.update_traces(yaxis="y2", name="Renewable share")
    fig_share_bar.add_traces(fig_share_line.data)

    fig_share_bar.update_layout(
        yaxis=dict(title="Renewable generation (GWh)"),
        yaxis2=dict(
            title="Share",
            overlaying="y",
            side="right",
            tickformat=".0%",
            range=[0, 1],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Chart 2: renewable generation by fuel/technology (Eurostat fuel aggregation)
    df_fuel = get_generation_by_fuel(country)  # country, year, fuel, generation_gwh
    df_fuel = df_fuel[(df_fuel["year"] >= start_year) & (df_fuel["year"] <= end_year)].copy()

    fig_fuel = px.bar(
        df_fuel,
        x="year",
        y="generation_gwh",
        color="fuel",
        labels={
            "year": "Year",
            "generation_gwh": "Generation (GWh)",
            "fuel": "Fuel / technology",
        },
        title=f"Renewable generation by fuel in {country}",
    )

    return fig_share_bar, fig_fuel