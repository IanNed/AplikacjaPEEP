import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import pandas as pd

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_share,
    get_generation_year_bounds,
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

layout = html.Div(
    [
        html.H2("Compare renewable generation share"),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Countries"),
                        dcc.Dropdown(
                            id="cr-countries",
                            options=COUNTRY_OPTIONS,
                            value=["PL", "DE"],  # default selection
                            multi=True,
                            clearable=False,
                        ),
                    ],
                    style={"width": "45%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Year range"),
                        dcc.RangeSlider(
                            id="cr-year-range",
                            min=MIN_YEAR,
                            max=MAX_YEAR,
                            value=[MIN_YEAR, MAX_YEAR],
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1, 2)},
                            allowCross=False,
                        ),
                    ],
                    style={"width": "45%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),
        html.H4("Renewable share of generation over time"),
        dcc.Graph(id="cr-share-graph"),
        html.H4("Latest-year summary"),
        dash_table.DataTable(
            id="cr-summary-table",
            columns=[],
            data=[],
            page_size=10,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
            style_header={"fontWeight": "bold"},
        ),
    ]
)


@callback(
    Output("cr-share-graph", "figure"),
    Output("cr-summary-table", "data"),
    Output("cr-summary-table", "columns"),
    Input("cr-countries", "value"),
    Input("cr-year-range", "value"),
)
def update_compare_renewables(countries, year_range):
    if not countries or not year_range:
        return px.Figure(), [], []

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    frames = []
    for country in countries:
        df_c = get_generation_share(country)  # year, renewable_generation_gwh, total_generation_gwh, renewable_share
        if df_c.empty:
            continue
        df_c = df_c.copy()
        df_c["country"] = country
        frames.append(df_c)

    if not frames:
        return px.Figure(), [], []

    df = pd.concat(frames, ignore_index=True)
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()

    if df.empty:
        return px.Figure(), [], []

    fig_share = px.line(
        df,
        x="year",
        y="renewable_share",
        color="country",
        markers=True,
        labels={
            "year": "Year",
            "renewable_share": "Renewable share of generation",
            "country": "Country",
        },
        title="Renewable share of net generation",
    )
    fig_share.update_yaxes(tickformat=".0%", range=[0, 1])

    latest_year = int(df["year"].max())
    df_latest = df[df["year"] == latest_year].copy()

    df_latest["renewable_share_pct"] = (df_latest["renewable_share"] * 100.0).round(1)
    df_latest["total_generation_gwh"] = df_latest["total_generation_gwh"].round(1)
    df_latest["renewable_generation_gwh"] = df_latest["renewable_generation_gwh"].round(1)

    df_view = df_latest[
        ["country", "year", "total_generation_gwh", "renewable_generation_gwh", "renewable_share_pct"]
    ].sort_values("country")

    columns = [
        {"name": "Country", "id": "country"},
        {"name": "Year", "id": "year"},
        {"name": "Total generation (GWh)", "id": "total_generation_gwh"},
        {"name": "Renewable generation (GWh)", "id": "renewable_generation_gwh"},
        {"name": "Renewable share (%)", "id": "renewable_share_pct"},
    ]

    return fig_share, df_view.to_dict("records"), columns