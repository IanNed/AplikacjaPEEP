import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px

from app.backend.data_access import (
    load_flow_totals,
    load_monthly_flows,
    get_total_border_flows,
    get_monthly_border_flows,
    get_border_partners,
)

dash.register_page(
    __name__,
    path="/interconnectors",
    name="Interconnectors",
    title="Interconnectors",
)

# Preload for options and date range
_flow_totals = load_flow_totals()        # country, partner, flow
_monthly_flows = load_monthly_flows()    # date, country, partner, flow

COUNTRY_OPTIONS = [
    {"label": c, "value": c}
    for c in sorted(_flow_totals["country"].unique())
]

MIN_DATE = _monthly_flows["date"].min()
MAX_DATE = _monthly_flows["date"].max()


layout = html.Div(
    [
        html.H2("Interconnectors"),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="ic-country",
                            options=COUNTRY_OPTIONS,
                            value=COUNTRY_OPTIONS[0]["value"] if COUNTRY_OPTIONS else None,
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Partner"),
                        dcc.Dropdown(
                            id="ic-partner",
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
                html.Div(
                    [
                        html.Label("Date range"),
                        dcc.DatePickerRange(
                            id="ic-date-range",
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
                        html.H4("Top interconnectors (total flow)"),
                        dcc.Graph(id="ic-top-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Monthly flow for selected border"),
                        dcc.Graph(id="ic-border-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),
    ]
)
@callback(
    Output("ic-partner", "options"),
    Output("ic-partner", "value"),
    Input("ic-country", "value"),
)
def update_partner_options(country):
    if not country:
        return [], None

    partners = get_border_partners(country)
    options = [{"label": p, "value": p} for p in partners]
    value = partners[0] if partners else None
    return options, value


@callback(
    Output("ic-top-graph", "figure"),
    Output("ic-border-graph", "figure"),
    Input("ic-country", "value"),
    Input("ic-partner", "value"),
    Input("ic-date-range", "start_date"),
    Input("ic-date-range", "end_date"),
)
def update_interconnectors(country, partner, start_date, end_date):
    if not country or not start_date or not end_date:
        return dash.no_update, dash.no_update

    # Top interconnectors by total flow for selected country
    df_top = get_total_border_flows()
    df_top_country = df_top.loc[df_top["country"] == country]

    fig_top = px.bar(
        df_top_country.head(15),
        x="partner",
        y="flow",
        labels={"partner": "Partner", "flow": "Total flow"},
        title=f"Top interconnectors for {country}",
    )

    # Monthly flow for selected border
    if not partner:
        return fig_top, dash.no_update

    df_border = get_monthly_border_flows(country, partner, start_date, end_date)

    fig_border = px.line(
        df_border,
        x="date",
        y="flow",
        markers=True,
        labels={"date": "Month", "flow": "Monthly flow"},
        title=f"Monthly flow {country} → {partner}",
    )

    return fig_top, fig_border