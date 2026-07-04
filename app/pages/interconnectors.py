import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from app.backend.data_access import (
    load_energy_flows,
    get_border_partners,
    get_top_partners_directional,
    get_border_flow_directional,
    get_interconnector_stats,
)

dash.register_page(
    __name__,
    path="/interconnectors",
    name="Interconnectors",
    title="Interconnectors",
)

# Preload for options and date range
_energy_flows = load_energy_flows()

COUNTRY_OPTIONS = [
    {"label": c, "value": c}
    for c in sorted(_energy_flows["country"].unique())
]

MIN_DATE = _energy_flows["date"].min()
MAX_DATE = _energy_flows["date"].max()

layout = html.Div(
    [
        html.H2("Interconnectors"),
        html.P(
            "Analyzes cross-border electricity flows with full import/export directionality. "
            "See which neighbours a country imports from vs exports to, and how the trade "
            "balance evolves over time.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Country"),
                        dcc.Dropdown(
                            id="ic-country",
                            options=COUNTRY_OPTIONS,
                            value="DE",
                            clearable=False,
                        ),
                    ],
                    style={"width": "25%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Partner"),
                        dcc.Dropdown(
                            id="ic-partner",
                            clearable=False,
                        ),
                    ],
                    style={"width": "25%", "display": "inline-block", "paddingLeft": "1.5rem"},
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
                    style={"width": "40%", "display": "inline-block", "paddingLeft": "1.5rem"},
                ),
            ],
            style={"marginBottom": "2rem"},
        ),

        # Section 1: Top partners (directional)
        html.H3("All Partners — Trade Balance"),
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Import vs Export by partner"),
                        dcc.Graph(id="ic-partners-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Net trade balance by partner"),
                        dcc.Graph(id="ic-balance-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Section 2: Selected border detail
        html.H3("Selected Border — Detailed View", style={"marginTop": "2rem"}),

        # Border KPIs
        html.Div(id="ic-border-kpis", style={"marginBottom": "1.5rem"}),

        # Border charts
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Monthly imports & exports"),
                        dcc.Graph(id="ic-directional-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H4("Net monthly flow (import − export)"),
                        dcc.Graph(id="ic-net-graph"),
                    ],
                    style={"width": "50%", "display": "inline-block"},
                ),
            ],
        ),

        # Cumulative flow
        html.H4("Cumulative net flow over time", style={"marginTop": "1.5rem"}),
        dcc.Graph(id="ic-cumulative-graph"),
    ]
)

# --- Callbacks ---

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
    Output("ic-partners-graph", "figure"),
    Output("ic-balance-graph", "figure"),
    Output("ic-border-kpis", "children"),
    Output("ic-directional-graph", "figure"),
    Output("ic-net-graph", "figure"),
    Output("ic-cumulative-graph", "figure"),
    Input("ic-country", "value"),
    Input("ic-partner", "value"),
    Input("ic-date-range", "start_date"),
    Input("ic-date-range", "end_date"),
)
def update_interconnectors(country, partner, start_date, end_date):
    empty_fig = go.Figure()

    if not country or not start_date or not end_date:
        return empty_fig, empty_fig, html.Div(), empty_fig, empty_fig, empty_fig

    # --- Section 1: All partners overview ---
    df_partners = get_top_partners_directional(country)

    if df_partners.empty:
        fig_partners = empty_fig
        fig_balance = empty_fig
    else:
        # Top 12 partners by total flow
        df_top = df_partners.head(12)

        # Stacked bar: import vs export
        fig_partners = go.Figure()

        fig_partners.add_trace(
            go.Bar(
                x=df_top["partner"],
                y=df_top["total_import_gwh"],
                name="Import (GWh)",
                marker_color="#4CAF50",
            )
        )
        fig_partners.add_trace(
            go.Bar(
                x=df_top["partner"],
                y=df_top["total_export_gwh"],
                name="Export (GWh)",
                marker_color="#FF7043",
            )
        )

        fig_partners.update_layout(
            barmode="group",
            title=f"Bilateral flows — {country} (all time)",
            xaxis_title="Partner",
            yaxis_title="Total flow (GWh)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # Net balance bar (diverging)
        fig_balance = go.Figure()

        fig_balance.add_trace(
            go.Bar(
                x=df_top["partner"],
                y=df_top["net_gwh"],
                marker_color=df_top["net_gwh"].apply(
                    lambda v: "#4CAF50" if v > 0 else "#F44336"
                ),
                text=df_top["net_gwh"].apply(lambda v: f"{v:+.0f}"),
                textposition="outside",
            )
        )

        fig_balance.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_balance.update_layout(
            title=f"Net trade balance — {country} (+ = imports from)",
            xaxis_title="Partner",
            yaxis_title="Net flow (GWh)",
            showlegend=False,
        )

    # --- Section 2: Selected border detail ---
    if not partner:
        return fig_partners, fig_balance, html.Div(), empty_fig, empty_fig, empty_fig

    df_border = get_border_flow_directional(country, partner, start_date, end_date)
    stats = get_interconnector_stats(country, partner, start_date, end_date)

    # Border KPIs
    if not stats:
        kpi_children = html.Div("No data for this border in selected period.", style={"color": "#999"})
    else:
        net_color = "#4CAF50" if stats["net_gwh"] > 0 else "#F44336"

        kpi_children = html.Div(
            style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"},
            children=[
                _kpi_card(
                    "Total Import",
                    f"{stats['total_import_gwh']:,.1f} GWh",
                    f"peak: {stats['peak_import_gwh']} GWh ({stats['peak_import_month'].strftime('%Y-%m')})",
                    value_color="#4CAF50",
                ),
                _kpi_card(
                    "Total Export",
                    f"{stats['total_export_gwh']:,.1f} GWh",
                    f"peak: {stats['peak_export_gwh']} GWh ({stats['peak_export_month'].strftime('%Y-%m')})",
                    value_color="#FF7043",
                ),
                _kpi_card(
                    "Net Balance",
                    f"{stats['net_gwh']:+,.1f} GWh",
                    stats["balance_label"],
                    value_color=net_color,
                ),
                _kpi_card(
                    "Months as Importer",
                    str(stats["months_net_importer"]),
                    f"vs {stats['months_net_exporter']} as exporter",
                ),
            ],
        )

    # Directional monthly chart (area: import up, export down)
    if df_border.empty:
        fig_directional = empty_fig
        fig_net = empty_fig
        fig_cumulative = empty_fig
    else:
        fig_directional = go.Figure()

        fig_directional.add_trace(
            go.Scatter(
                x=df_border["date"],
                y=df_border["import_gwh"],
                mode="lines",
                name="Import",
                fill="tozeroy",
                line=dict(color="#4CAF50"),
                fillcolor="rgba(76,175,80,0.3)",
            )
        )

        fig_directional.add_trace(
            go.Scatter(
                x=df_border["date"],
                y=-df_border["export_gwh"],
                mode="lines",
                name="Export",
                fill="tozeroy",
                line=dict(color="#FF7043"),
                fillcolor="rgba(255,112,67,0.3)",
            )
        )

        fig_directional.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_directional.update_layout(
            title=f"Monthly flows — {country} ↔ {partner}",
            xaxis_title="Month",
            yaxis_title="GWh (imports ↑ / exports ↓)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # Net flow bar chart
        fig_net = go.Figure()

        fig_net.add_trace(
            go.Bar(
                x=df_border["date"],
                y=df_border["net_gwh"],
                marker_color=df_border["net_gwh"].apply(
                    lambda v: "#4CAF50" if v >= 0 else "#F44336"
                ),
                name="Net flow",
            )
        )

        fig_net.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_net.update_layout(
            title=f"Net monthly — {country} → {partner} (+ = importing)",
            xaxis_title="Month",
            yaxis_title="Net flow (GWh)",
            showlegend=False,
        )

        # Cumulative net flow
        df_border["cumulative_net"] = df_border["net_gwh"].cumsum()

        fig_cumulative = go.Figure()

        fig_cumulative.add_trace(
            go.Scatter(
                x=df_border["date"],
                y=df_border["cumulative_net"],
                mode="lines",
                fill="tozeroy",
                line=dict(color="#1565C0", width=2),
                fillcolor="rgba(21,101,192,0.15)",
                name="Cumulative net",
            )
        )

        fig_cumulative.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_cumulative.update_layout(
            title=f"Cumulative net flow — {country} ↔ {partner}",
            xaxis_title="Month",
            yaxis_title="Cumulative net (GWh)",
            showlegend=False,
            annotations=[
                dict(
                    x=df_border["date"].iloc[-1],
                    y=df_border["cumulative_net"].iloc[-1],
                    text=f"Total: {df_border['cumulative_net'].iloc[-1]:+,.1f} GWh",
                    showarrow=True,
                    arrowhead=2,
                    ax=-50,
                    ay=-30,
                )
            ],
        )

    return fig_partners, fig_balance, kpi_children, fig_directional, fig_net, fig_cumulative

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
            "minWidth": "140px",
            "padding": "0.8rem",
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
            "textAlign": "center",
            "backgroundColor": "#fafafa",
        },
    )
