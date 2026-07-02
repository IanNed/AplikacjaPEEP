import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import pandas as pd

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_share,
    get_generation_year_bounds,
    get_annual_load,
)

dash.register_page(
    __name__,
    path="/renewables-vs-load",
    name="Renewables vs load",
    title="Renewables vs load",
)

# Eurostat annual renewable share dataset drives the country list and year bounds
_eu_df = load_eurostat_share_annual()
COUNTRY_OPTIONS = [{"label": c, "value": c} for c in sorted(_eu_df["country"].unique())]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

layout = html.Div(
    [
        html.H2("Renewables vs demand (Eurostat generation + ENTSO-E load)"),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="rvl-country",
                            options=COUNTRY_OPTIONS,
                            value="PL",
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
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1, 2)},
                            allowCross=False,
                        ),
                    ],
                    style={"width": "65%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),
        html.H4("Annual generation, load, and renewable share"),
        dash_table.DataTable(
            id="rvl-table",
            columns=[],
            data=[],
            page_size=20,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
            style_header={"fontWeight": "bold"},
        ),
        html.H4("Renewable share of generation over time"),
        dcc.Graph(id="rvl-share-graph"),
    ]
)


@callback(
    Output("rvl-table", "data"),
    Output("rvl-table", "columns"),
    Output("rvl-share-graph", "figure"),
    Input("rvl-country", "value"),
    Input("rvl-year-range", "value"),
)
def update_renewables_vs_load_table(country, year_range):
    if not country or not year_range:
        return [], [], px.Figure()

    start_year, end_year = year_range

    # Eurostat annual generation and share for this country
    df_gen = get_generation_share(country)  # year, renewable_generation_gwh, total_generation_gwh, renewable_share

    # ENTSO-E annual load
    df_load = get_annual_load(country)     # year, annual_load_mwh

    if df_gen.empty or df_load.empty:
        return [], [], px.Figure()

    # Merge on year
    df = df_gen.merge(df_load, on="year", how="inner")
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()

    if df.empty:
        return [], [], px.Figure()

    # MWh to GWh conversion
    df["annual_load_gwh"] = df["annual_load_mwh"] / 1000.0

    # Compute load to generation ratio
    df["load_to_generation_ratio"] = df["annual_load_gwh"] / df["total_generation_gwh"]

    # Prepare table view
    df_view = df.copy()
    df_view["renewable_share_pct"] = (df_view["renewable_share"] * 100.0).round(1)
    df_view["total_generation_gwh"] = df_view["total_generation_gwh"].round(1)
    df_view["renewable_generation_gwh"] = df_view["renewable_generation_gwh"].round(1)
    df_view["annual_load_gwh"] = df_view["annual_load_gwh"].round(1)
    df_view["load_to_generation_ratio"] = df_view["load_to_generation_ratio"].round(2)

    df_view = df_view[
        [
            "year",
            "total_generation_gwh",
            "renewable_generation_gwh",
            "renewable_share_pct",
            "annual_load_gwh",
            "load_to_generation_ratio",
        ]
    ].sort_values("year")

    columns = [
        {"name": "Year", "id": "year"},
        {"name": "Total generation (GWh)", "id": "total_generation_gwh"},
        {"name": "Renewable generation (GWh)", "id": "renewable_generation_gwh"},
        {"name": "Renewable share (%)", "id": "renewable_share_pct"},
        {"name": "Annual load (GWh)", "id": "annual_load_gwh"},
        {"name": "Load / generation (GWh/GWh)", "id": "load_to_generation_ratio"},
    ]

    # Share line chart
    fig_share = px.line(
        df,
        x="year",
        y="renewable_share",
        markers=True,
        labels={
            "year": "Year",
            "renewable_share": "Renewable share of generation",
        },
        title=f"Renewable share of net generation in {country}",
    )
    fig_share.update_yaxes(tickformat=".0%", range=[0, 1])

    return df_view.to_dict("records"), columns, fig_share