import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_energy_flows,
    get_border_partners,
    get_top_partners_directional,
    get_border_flow_directional,
    get_interconnector_stats,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card, kpi_card, kpi_row,
    section_header,
)

dash.register_page(
    __name__,
    path="/interconnectors",
    name="Połączenia transgraniczne",
    title="Połączenia transgraniczne",
)

# Preload for options and date range
_energy_flows = load_energy_flows()

COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_energy_flows["country"].unique())
]

MIN_DATE = _energy_flows["date"].min()
MAX_DATE = _energy_flows["date"].max()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Połączenia transgraniczne",
        "Analiza transgranicznych przepływów energii elektrycznej z pełnym rozróżnieniem importu i eksportu. "
        "Sprawdź, od których sąsiadów kraj importuje, a do których eksportuje, oraz jak bilans handlowy "
        "zmienia się w czasie."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraj", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="ic-country",
                    options=COUNTRY_OPTIONS,
                    value="PL",
                    clearable=False,
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("Partner", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="ic-partner",
                    clearable=False,
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("Zakres dat", style={"color": "#ccc"}),
                dcc.DatePickerRange(
                    id="ic-date-range",
                    min_date_allowed=MIN_DATE,
                    max_date_allowed=MAX_DATE,
                    start_date=MIN_DATE,
                    end_date=MAX_DATE,
                    display_format="YYYY-MM",
                ),
            ], md=6),
        ]),
    ),

    # Section 1: Selected border detail
    section_header("Wybrane połączenie — widok szczegółowy"),

    # Border KPIs
    html.Div(id="ic-border-kpis", className="mb-4"),

    # Border charts
    dbc.Row([
        dbc.Col(chart_card("Miesięczny import i eksport", "ic-directional-graph"), md=6),
        dbc.Col(chart_card("Przepływ netto (import − eksport)", "ic-net-graph"), md=6),
    ]),

    # Cumulative flow
    section_header("Skumulowany przepływ netto w czasie"),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="ic-cumulative-graph", style={"height": "400px"}),
            style={"padding": "0.5rem"},
        ),
        className="mb-3",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),

    # Section 2: All partners overview
    section_header("Wszyscy partnerzy — bilans handlowy"),
    dbc.Row([
        dbc.Col(chart_card("Import vs eksport wg partnera", "ic-partners-graph"), md=6),
        dbc.Col(chart_card("Bilans handlowy netto wg partnera", "ic-balance-graph"), md=6),
    ]),

])

# -----------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------

@callback(
    Output("ic-partner", "options"),
    Output("ic-partner", "value"),
    Input("ic-country", "value"),
)
def update_partner_options(country):
    if not country:
        return [], None

    partners = get_border_partners(country)
    options = [{"label": COUNTRY_NAMES_PL.get(p, p), "value": p} for p in partners]
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

    country_name = COUNTRY_NAMES_PL.get(country, country)
    partner_name = COUNTRY_NAMES_PL.get(partner, partner) if partner else ""

    # --- Section 1: All partners overview ---
    df_partners = get_top_partners_directional(country)

    if df_partners.empty:
        fig_partners = empty_fig
        fig_balance = empty_fig
    else:
        df_top = df_partners.head(12).copy()
        df_top["partner_name"] = df_top["partner"].map(COUNTRY_NAMES_PL)

        # Grouped bar: import vs export
        fig_partners = go.Figure()

        fig_partners.add_trace(
            go.Bar(
                x=df_top["partner_name"],
                y=df_top["total_import_gwh"],
                name="Import (GWh)",
                marker_color="#00d4aa",
            )
        )
        fig_partners.add_trace(
            go.Bar(
                x=df_top["partner_name"],
                y=df_top["total_export_gwh"],
                name="Eksport (GWh)",
                marker_color="#f97316",
            )
        )

        fig_partners.update_layout(
            barmode="group",
            title=f"Przepływy bilateralne — {country_name} (cały okres)",
            xaxis_title="Partner",
            yaxis_title="Przepływ całkowity (GWh)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # Net balance bar (diverging)
        fig_balance = go.Figure()

        fig_balance.add_trace(
            go.Bar(
                x=df_top["partner_name"],
                y=df_top["net_gwh"],
                marker_color=df_top["net_gwh"].apply(
                    lambda v: "#00d4aa" if v > 0 else "#ff6b6b"
                ),
                text=df_top["net_gwh"].apply(lambda v: f"{v:+.0f}"),
                textposition="outside",
                textfont=dict(color="#ccc"),
            )
        )

        fig_balance.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        fig_balance.update_layout(
            title=f"Bilans netto — {country_name} (+ = import od)",
            xaxis_title="Partner",
            yaxis_title="Przepływ netto (GWh)",
            showlegend=False,
        )

    # --- Section 2: Selected border detail ---
    if not partner:
        return fig_partners, fig_balance, html.Div(), empty_fig, empty_fig, empty_fig

    df_border = get_border_flow_directional(country, partner, start_date, end_date)
    stats = get_interconnector_stats(country, partner, start_date, end_date)

    # Border KPIs
    if not stats:
        kpi_children = html.Div("Brak danych dla tego połączenia w wybranym okresie.", style={"color": "#999", "padding": "1rem"})
    else:
        net_color = "#00d4aa" if stats["net_gwh"] > 0 else "#ff6b6b"
        balance_label_pl = "Importer netto" if stats["net_gwh"] > 0 else "Eksporter netto"

        kpi_children = kpi_row([
            kpi_card(
                "Import łączny",
                f"{stats['total_import_gwh']:,.1f} GWh",
                f"szczyt: {stats['peak_import_gwh']} GWh ({stats['peak_import_month'].strftime('%Y-%m')})",
                value_color="#00d4aa",
            ),
            kpi_card(
                "Eksport łączny",
                f"{stats['total_export_gwh']:,.1f} GWh",
                f"szczyt: {stats['peak_export_gwh']} GWh ({stats['peak_export_month'].strftime('%Y-%m')})",
                value_color="#f97316",
            ),
            kpi_card(
                "Bilans netto",
                f"{stats['net_gwh']:+,.1f} GWh",
                balance_label_pl,
                value_color=net_color,
            ),
            kpi_card(
                "Miesiące jako importer",
                str(stats["months_net_importer"]),
                f"vs {stats['months_net_exporter']} jako eksporter",
            ),
        ])

    # Directional monthly chart
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
                line=dict(color="#00d4aa"),
                fillcolor="rgba(0,212,170,0.2)",
            )
        )

        fig_directional.add_trace(
            go.Scatter(
                x=df_border["date"],
                y=-df_border["export_gwh"],
                mode="lines",
                name="Eksport",
                fill="tozeroy",
                line=dict(color="#f97316"),
                fillcolor="rgba(249,115,22,0.2)",
            )
        )

        fig_directional.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        fig_directional.update_layout(
            title=f"Przepływy miesięczne — {country_name} ↔ {partner_name}",
            xaxis_title="Miesiąc",
            yaxis_title="GWh (import ↑ / eksport ↓)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # Net flow bar chart
        fig_net = go.Figure()

        fig_net.add_trace(
            go.Bar(
                x=df_border["date"],
                y=df_border["net_gwh"],
                marker_color=df_border["net_gwh"].apply(
                    lambda v: "#00d4aa" if v >= 0 else "#ff6b6b"
                ),
                name="Przepływ netto",
            )
        )

        fig_net.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        fig_net.update_layout(
            title=f"Netto miesięcznie — {country_name} → {partner_name} (+ = import)",
            xaxis_title="Miesiąc",
            yaxis_title="Przepływ netto (GWh)",
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
                line=dict(color="#3391ff", width=2),
                fillcolor="rgba(51,145,255,0.12)",
                name="Skumulowane netto",
            )
        )

        fig_cumulative.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        fig_cumulative.update_layout(
            title=f"Skumulowany przepływ netto — {country_name} ↔ {partner_name}",
            xaxis_title="Miesiąc",
            yaxis_title="Skumulowane netto (GWh)",
            showlegend=False,
            annotations=[
                dict(
                    x=df_border["date"].iloc[-1],
                    y=df_border["cumulative_net"].iloc[-1],
                    text=f"Suma: {df_border['cumulative_net'].iloc[-1]:+,.1f} GWh",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#ccc",
                    ax=-50,
                    ay=-30,
                    font=dict(color="#ccc"),
                )
            ],
        )

    return fig_partners, fig_balance, kpi_children, fig_directional, fig_net, fig_cumulative
