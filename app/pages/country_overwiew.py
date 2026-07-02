import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import pandas as pd

from app.backend.data_access import (
    load_monthly,
    get_monthly_load,
    get_net_country_flows,
    get_country_totals,
)       

dash.register_page(
    __name__,
    path="/country-overview",
    name="Country overview",
    title="Country overview",
)

# Preload monthly data to get available countries and min/max dates
_monthly_df = load_monthly()  # columns: country, year_month, load_sum, load_mean, load_peak[file:50]

COUNTRY_OPTIONS = [
    {"label": c, "value": c}
    for c in sorted(_monthly_df["country"].unique())
]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()


layout = html.Div(
    [
        html.H2("Country overview"),

        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="co-country",
                            options=COUNTRY_OPTIONS,
                            value="DE",  # pick your favourite default
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Date range"),
                        dcc.DatePickerRange(
                            id="co-date-range",
                            min_date_allowed=MIN_DATE,
                            max_date_allowed=MAX_DATE,
                            initial_visible_month=MIN_DATE,
                            start_date=MIN_DATE,
                            end_date=MAX_DATE,
                            display_format="YYYY-MM",
                        ),
                    ],
                    style={"width": "60%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        html.Div(
            [
                html.Div(
                    [
                        html.H4("Monthly load"),
                        dcc.Graph(id="co-load-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Net cross-border imports"),
                        dcc.Graph(id="co-netflow-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),

        html.Div(
            [
                html.H4("Country totals (full period)"),
                html.Div(id="co-kpis"),
            ],
            style={"marginTop": "2rem"},
        ),
    ]
)

@callback(
    Output("co-load-graph", "figure"),
    Output("co-netflow-graph", "figure"),
    Output("co-kpis", "children"),
    Input("co-country", "value"),
    Input("co-date-range", "start_date"),
    Input("co-date-range", "end_date"),
)
def update_country_overview(country, start_date, end_date):
    if not country or not start_date or not end_date:
        # initial render or invalid inputs
        return dash.no_update, dash.no_update, dash.no_update

    # Monthly load: uses monthly_load.csv (country, year_month, load_sum...)[file:50]
    df_load = get_monthly_load(country, start_date, end_date)

    fig_load = px.line(
        df_load,
        x="year_month",
        y="load_sum",
        markers=True,
        labels={"year_month": "Month", "load_sum": "Monthly load"},
        title=f"Monthly load for {country}",
    )

    # Net flows: imports positive, exports negative
    df_flow = get_net_country_flows(country, start_date, end_date)

    fig_flow = px.line(
        df_flow,
        x="date",
        y="net_flow",
        markers=True,
        labels={"date": "Month", "net_flow": "Net imports (+) / exports (-)"},
        title=f"Net cross-border flows for {country}",
    )
    fig_flow.add_hline(y=0, line_dash="dash", line_color="gray")

    # KPIs from full-period totals
    totals = get_country_totals()
    row = totals.loc[totals["country"] == country].iloc[0]
    total_import = row["total_import"]
    total_export = row["total_export"]
    net = total_export - total_import

    kpi_children = html.Div(
        style={"display": "flex", "gap": "2rem"},
        children=[
            html.Div(
                [html.Div("Total imports"), html.Div(f"{total_import:,.0f}")],
                style={"flex": 1},
            ),
            html.Div(
                [html.Div("Total exports"), html.Div(f"{total_export:,.0f}")],
                style={"flex": 1},
            ),
            html.Div(
                [html.Div("Net (export - import)"), html.Div(f"{net:,.0f}")],
                style={"flex": 1},
            ),
        ],
    )

    return fig_load, fig_flow, kpi_children