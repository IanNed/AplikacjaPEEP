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
    path="/compare-countries",
    name="Compare countries",
    title="Compare countries",
)

# Preload monthly data to get countries and date range
_monthly_df = load_monthly()  # country, year_month, load_sum, load_mean, load_peak
COUNTRIES = sorted(_monthly_df["country"].unique())

COUNTRY_OPTIONS = [{"label": c, "value": c} for c in COUNTRIES]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()


layout = html.Div(
    [
        html.H2("Compare countries"),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country A"),
                        dcc.Dropdown(
                            id="cc-country-a",
                            options=COUNTRY_OPTIONS,
                            value="DE",  # defaults; adjust if you prefer
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Country B"),
                        dcc.Dropdown(
                            id="cc-country-b",
                            options=COUNTRY_OPTIONS,
                            value="FR",
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
                html.Div(
                    [
                        html.Label("Date range"),
                        dcc.DatePickerRange(
                            id="cc-date-range",
                            min_date_allowed=MIN_DATE,
                            max_date_allowed=MAX_DATE,
                            start_date=MIN_DATE,
                            end_date=MAX_DATE,
                            display_format="YYYY-MM",
                        ),
                    ],
                    style={"width": "35%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        # Charts
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Monthly load"),
                        dcc.Graph(id="cc-load-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Net cross-border flows"),
                        dcc.Graph(id="cc-netflow-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),

        # KPIs
        html.Div(
            [
                html.H4("Full-period totals"),
                html.Div(id="cc-kpis"),
            ],
            style={"marginTop": "2rem"},
        ),
    ]
)
@callback(
    Output("cc-load-graph", "figure"),
    Output("cc-netflow-graph", "figure"),
    Output("cc-kpis", "children"),
    Input("cc-country-a", "value"),
    Input("cc-country-b", "value"),
    Input("cc-date-range", "start_date"),
    Input("cc-date-range", "end_date"),
)
def update_comparison(country_a, country_b, start_date, end_date):
    if not country_a or not country_b or not start_date or not end_date:
        return dash.no_update, dash.no_update, dash.no_update

    # Monthly load
    df_a_load = get_monthly_load(country_a, start_date, end_date)
    df_b_load = get_monthly_load(country_b, start_date, end_date)

    df_a_load["country"] = country_a
    df_b_load["country"] = country_b
    df_load = pd.concat([df_a_load, df_b_load], ignore_index=True)

    fig_load = px.line(
        df_load,
        x="year_month",
        y="load_sum",
        color="country",
        markers=True,
        labels={"year_month": "Month", "load_sum": "Monthly load"},
        title=f"Monthly load: {country_a} vs {country_b}",
    )

    # Net flows
    df_a_flow = get_net_country_flows(country_a, start_date, end_date)
    df_b_flow = get_net_country_flows(country_b, start_date, end_date)

    df_a_flow["country"] = country_a
    df_b_flow["country"] = country_b
    df_flow = pd.concat([df_a_flow, df_b_flow], ignore_index=True)

    fig_flow = px.line(
        df_flow,
        x="date",
        y="net_flow",
        color="country",
        markers=True,
        labels={"date": "Month", "net_flow": "Net imports (+) / exports (-)"},
        title=f"Net cross-border flows: {country_a} vs {country_b}",
    )
    fig_flow.add_hline(y=0, line_dash="dash", line_color="gray")

    # KPIs from full-period totals
    totals = get_country_totals()

    row_a = totals.loc[totals["country"] == country_a].iloc[0]
    row_b = totals.loc[totals["country"] == country_b].iloc[0]

    imp_a, exp_a = row_a["total_import"], row_a["total_export"]
    imp_b, exp_b = row_b["total_import"], row_b["total_export"]

    net_a = exp_a - imp_a
    net_b = exp_b - imp_b

    kpi_children = html.Div(
        style={"display": "flex", "gap": "2rem"},
        children=[
            html.Div(
                [
                    html.H5(country_a),
                    html.Div(f"Total imports: {imp_a:,.0f}"),
                    html.Div(f"Total exports: {exp_a:,.0f}"),
                    html.Div(f"Net (export - import): {net_a:,.0f}"),
                ],
                style={"flex": 1},
            ),
            html.Div(
                [
                    html.H5(country_b),
                    html.Div(f"Total imports: {imp_b:,.0f}"),
                    html.Div(f"Total exports: {exp_b:,.0f}"),
                    html.Div(f"Net (export - import): {net_b:,.0f}"),
                ],
                style={"flex": 1},
            ),
        ],
    )

    return fig_load, fig_flow, kpi_children