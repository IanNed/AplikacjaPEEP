import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from app.backend.data_access import (
    load_monthly,
    get_monthly_load,
    get_net_country_flows,
    get_country_overview_kpis,
    get_annual_load_summary,
)

dash.register_page(
    __name__,
    path="/country-overview",
    name="Country overview",
    title="Country overview",
)

# Preload monthly data to get available countries and min/max dates
_monthly_df = load_monthly()

COUNTRY_OPTIONS = [
    {"label": c, "value": c}
    for c in sorted(_monthly_df["country"].unique())
]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()

layout = html.Div(
    [
        html.H2("Country Overview"),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="co-country",
                            options=COUNTRY_OPTIONS,
                            value="DE",
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
            style={"marginBottom": "1.5rem"},
        ),

        # KPI cards row
        html.Div(id="co-kpis", style={"marginBottom": "2rem"}),

        # Charts row 1: monthly load + net flows
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
                        html.H4("Net cross-border flows"),
                        dcc.Graph(id="co-netflow-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ]
        ),

        # Charts row 2: annual summary + load factor
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Annual load & peak demand"),
                        dcc.Graph(id="co-annual-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Annual load factor"),
                        dcc.Graph(id="co-loadfactor-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
            style={"marginTop": "1rem"},
        ),
    ]
)

@callback(
    Output("co-kpis", "children"),
    Output("co-load-graph", "figure"),
    Output("co-netflow-graph", "figure"),
    Output("co-annual-graph", "figure"),
    Output("co-loadfactor-graph", "figure"),
    Input("co-country", "value"),
    Input("co-date-range", "start_date"),
    Input("co-date-range", "end_date"),
)
def update_country_overview(country, start_date, end_date):
    empty_fig = go.Figure()

    if not country or not start_date or not end_date:
        return html.Div(), empty_fig, empty_fig, empty_fig, empty_fig

    # --- KPI cards ---
    kpis = get_country_overview_kpis(country, start_date, end_date)

    if not kpis:
        kpi_children = html.Div("No data available.", style={"color": "red"})
    else:
        # YoY indicator
        yoy = kpis.get("yoy_load_change_pct")
        if yoy is not None:
            yoy_text = f"{yoy:+.1f}%"
            yoy_color = "#4CAF50" if yoy > 0 else "#F44336"
        else:
            yoy_text = "N/A"
            yoy_color = "#999"

        # Renewable share
        ren_share = kpis.get("renewable_share_pct")
        ren_year = kpis.get("renewable_year")
        ren_text = f"{ren_share:.1f}%" if ren_share is not None else "N/A"
        ren_subtitle = f"Eurostat {ren_year}" if ren_year else ""

        kpi_children = html.Div(
            style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"},
            children=[
                _kpi_card(
                    "Total Load",
                    f"{kpis['total_load_twh']:.1f} TWh",
                    "in selected period",
                ),
                _kpi_card(
                    "Avg Monthly Load",
                    f"{kpis['avg_monthly_load_gwh']:.0f} GWh",
                    "monthly average",
                ),
                _kpi_card(
                    "Peak Demand",
                    f"{kpis['peak_demand_mw']:,.0f} MW",
                    f"recorded {kpis['peak_demand_month'].strftime('%Y-%m')}",
                ),
                _kpi_card(
                    "Load Factor",
                    f"{kpis['load_factor']:.2f}",
                    "avg/peak (1.0 = perfectly flat)",
                ),
                _kpi_card(
                    "YoY Load Change",
                    yoy_text,
                    "latest full year vs prior",
                    value_color=yoy_color,
                ),
                _kpi_card(
                    "Renewable Share",
                    ren_text,
                    ren_subtitle,
                    value_color="#4CAF50" if ren_share and ren_share > 40 else "#FF9800",
                ),
                _kpi_card(
                    "Trade Position",
                    kpis["net_position_label"],
                    f"Net: {kpis['net_position_gwh']:+,.0f} GWh",
                    value_color="#1565C0" if kpis["net_position_gwh"] > 0 else "#E65100",
                ),
            ],
        )

    # --- Monthly load chart (with peak overlay) ---
    df_load = get_monthly_load(country, start_date, end_date)

    fig_load = make_subplots(specs=[[{"secondary_y": True}]])

    fig_load.add_trace(
        go.Bar(
            x=df_load["year_month"],
            y=df_load["load_sum"],
            name="Monthly load (MWh)",
            marker_color="#1976D2",
            opacity=0.7,
        ),
        secondary_y=False,
    )

    fig_load.add_trace(
        go.Scatter(
            x=df_load["year_month"],
            y=df_load["load_peak"],
            mode="lines+markers",
            name="Peak demand (MW)",
            line=dict(color="#F44336", width=2),
            marker=dict(size=4),
        ),
        secondary_y=True,
    )

    fig_load.update_layout(
        title=f"Monthly load — {country}",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_load.update_yaxes(title_text="Monthly load (MWh)", secondary_y=False)
    fig_load.update_yaxes(title_text="Peak demand (MW)", secondary_y=True)
    fig_load.update_xaxes(title_text="Month")

    # --- Net flows chart ---
    df_flow = get_net_country_flows(country, start_date, end_date)

    if df_flow.empty:
        fig_flow = empty_fig
    else:
        fig_flow = go.Figure()

        fig_flow.add_trace(
            go.Bar(
                x=df_flow["date"],
                y=df_flow["net_flow"],
                marker_color=df_flow["net_flow"].apply(
                    lambda v: "#4CAF50" if v >= 0 else "#F44336"
                ),
                name="Net flow",
            )
        )

        fig_flow.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_flow.update_layout(
            title=f"Net cross-border flows — {country}",
            xaxis_title="Month",
            yaxis_title="Net imports (+) / exports (−)",
            showlegend=False,
        )

    # --- Annual summary chart (bar + line) ---
    df_annual = get_annual_load_summary(country)

    if df_annual.empty:
        fig_annual = empty_fig
        fig_lf = empty_fig
    else:
        fig_annual = make_subplots(specs=[[{"secondary_y": True}]])

        fig_annual.add_trace(
            go.Bar(
                x=df_annual["year"],
                y=df_annual["annual_load_twh"],
                name="Annual load (TWh)",
                marker_color="#42A5F5",
            ),
            secondary_y=False,
        )

        fig_annual.add_trace(
            go.Scatter(
                x=df_annual["year"],
                y=df_annual["peak_mw"],
                mode="lines+markers",
                name="Peak demand (MW)",
                line=dict(color="#EF5350", width=2),
            ),
            secondary_y=True,
        )

        fig_annual.update_layout(
            title=f"Annual load & peak — {country}",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_annual.update_yaxes(title_text="Annual load (TWh)", secondary_y=False)
        fig_annual.update_yaxes(title_text="Peak demand (MW)", secondary_y=True)
        fig_annual.update_xaxes(title_text="Year")

        # Load factor chart
        fig_lf = px.line(
            df_annual,
            x="year",
            y="load_factor",
            markers=True,
            labels={"year": "Year", "load_factor": "Load factor"},
            title=f"Load factor trend — {country}",
        )
        fig_lf.update_yaxes(range=[0, 1], tickformat=".2f")
        fig_lf.add_hline(
            y=df_annual["load_factor"].mean(),
            line_dash="dot",
            line_color="#999",
            annotation_text=f"Avg: {df_annual['load_factor'].mean():.3f}",
            annotation_position="top right",
        )

    return kpi_children, fig_load, fig_flow, fig_annual, fig_lf

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
            "minWidth": "130px",
            "padding": "0.8rem",
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
            "textAlign": "center",
            "backgroundColor": "#fafafa",
        },
    )
