import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import pandas as pd

from app.backend.data_access import (
    load_daily,
    get_daily_load,
    get_intraday_profile,
)

dash.register_page(
    __name__,
    path="/load-patterns",
    name="Load patterns",
    title="Load patterns",
)

# Preload daily data to get countries and date range
_daily_df = load_daily()  # country, date, load_sum, load_mean, load_peak

COUNTRY_OPTIONS = [
    {"label": c, "value": c}
    for c in sorted(_daily_df["country"].unique())
]

MIN_DATE = _daily_df["date"].min()
MAX_DATE = _daily_df["date"].max()


layout = html.Div(
    [
        html.H2("Load patterns"),

        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="lp-country",
                            options=COUNTRY_OPTIONS,
                            value="DE",  # or your preferred default
                            clearable=False,
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Analysis window"),
                        dcc.DatePickerRange(
                            id="lp-date-range",
                            min_date_allowed=MIN_DATE,
                            max_date_allowed=MAX_DATE,
                            start_date=MIN_DATE,
                            end_date=MIN_DATE + pd.Timedelta(days=30),
                            display_format="YYYY-MM-DD",
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
                        html.H4("Daily load"),
                        dcc.Graph(id="lp-daily-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Intraday profile (average by hour)"),
                        dcc.Graph(id="lp-intraday-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),
    ]
)
@callback(
    Output("lp-daily-graph", "figure"),
    Output("lp-intraday-graph", "figure"),
    Input("lp-country", "value"),
    Input("lp-date-range", "start_date"),
    Input("lp-date-range", "end_date"),
)
def update_load_patterns(country, start_date, end_date):
    if not country or not start_date or not end_date:
        return dash.no_update, dash.no_update

    # Daily view
    df_daily = get_daily_load(country, start_date, end_date)

    fig_daily = px.line(
        df_daily,
        x="date",
        y="load_sum",
        markers=True,
        labels={"date": "Date", "load_sum": "Daily load"},
        title=f"Daily load for {country}",
    )

    # Intraday profile (only makes sense for reasonably small windows)
    df_profile = get_intraday_profile(country, start_date, end_date)

    if df_profile.empty:
        fig_intraday = px.scatter(
            x=[],
            y=[],
            title="No hourly data in selected window",
        )
    else:
        fig_intraday = px.line(
            df_profile,
            x="hour",
            y="load_mean",
            markers=True,
            labels={"hour": "Hour of day", "load_mean": "Average load"},
            title=f"Average hourly profile for {country}",
        )

    return fig_daily, fig_intraday