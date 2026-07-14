import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_monthly,
    get_monthly_load_clean,
    get_net_country_flows,
    get_country_overview_kpis,
    get_annual_load_summary,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card, kpi_card, kpi_row,
)

dash.register_page(
    __name__,
    path="/country-overview",
    name="Przegląd kraju",
    title="Przegląd kraju",
)

# Preload monthly data to get available countries and min/max dates
_monthly_df = load_monthly()

COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_monthly_df["country"].unique())
]

MIN_DATE = _monthly_df["year_month"].min()
MAX_DATE = _monthly_df["year_month"].max()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Przegląd kraju",
        "Kompleksowa analiza elektroenergetyczna wybranego kraju: obciążenie, szczytowe "
        "zapotrzebowanie, przepływy transgraniczne i kluczowe wskaźniki wydajności."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraj", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="co-country",
                    options=COUNTRY_OPTIONS,
                    value="PL",
                    clearable=False,
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Zakres dat", style={"color": "#ccc"}),
                dcc.DatePickerRange(
                    id="co-date-range",
                    min_date_allowed=MIN_DATE,
                    max_date_allowed=MAX_DATE,
                    initial_visible_month=MIN_DATE,
                    start_date=MIN_DATE,
                    end_date=MAX_DATE,
                    display_format="YYYY-MM",
                ),
            ], md=8),
        ]),
    ),

    # KPI cards row
    html.Div(id="co-kpis", className="mb-4"),

    # Charts row 1: monthly load + net flows
    dbc.Row([
        dbc.Col(chart_card("Obciążenie miesięczne", "co-load-graph"), md=6),
        dbc.Col(chart_card("Przepływy transgraniczne netto", "co-netflow-graph"), md=6),
    ]),

    # Charts row 2: annual summary + load factor
    dbc.Row([
        dbc.Col(chart_card("Obciążenie roczne i szczyt zapotrzebowania", "co-annual-graph"), md=6),
        dbc.Col(chart_card("Roczny współczynnik obciążenia", "co-loadfactor-graph"), md=6),
    ]),
])

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

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

    country_name = COUNTRY_NAMES_PL.get(country, country)

    # --- KPI cards ---
    kpis = get_country_overview_kpis(country, start_date, end_date)

    if not kpis:
        kpi_children = html.Div("Brak dostępnych danych.", style={"color": "#ff6b6b", "padding": "1rem"})
    else:
        # YoY indicator
        yoy = kpis.get("yoy_load_change_pct")
        if yoy is not None:
            yoy_text = f"{yoy:+.1f}%"
            yoy_color = "#00d4aa" if yoy > 0 else "#ff6b6b"
        else:
            yoy_text = "N/A"
            yoy_color = "#999"

        # Renewable share
        ren_share = kpis.get("renewable_share_pct")
        ren_year = kpis.get("renewable_year")
        ren_text = f"{ren_share:.1f}%" if ren_share is not None else "N/A"
        ren_subtitle = f"Eurostat {ren_year}" if ren_year else ""
        ren_color = "#00d4aa" if ren_share and ren_share > 40 else "#ffd93d"

        # Trade position
        trade_color = "#3391ff" if kpis["net_position_gwh"] > 0 else "#f97316"
        trade_label = "Eksporter netto" if kpis["net_position_gwh"] > 0 else "Importer netto"

        kpi_children = kpi_row([
            kpi_card(
                "Obciążenie łączne",
                f"{kpis['total_load_twh']:.1f} TWh",
                "w wybranym okresie",
            ),
            kpi_card(
                "Śr. miesięczne",
                f"{kpis['avg_monthly_load_gwh']:.0f} GWh",
                "średnia miesięczna",
            ),
            kpi_card(
                "Szczyt zapotrzebowania",
                f"{kpis['peak_demand_mw']:,.0f} MW",
                f"zarejestrowany {kpis['peak_demand_month'].strftime('%Y-%m')}",
                value_color="#ff6b6b",
            ),
            kpi_card(
                "Wsp. obciążenia",
                f"{kpis['load_factor']:.2f}",
                "śr./szczyt (1.0 = idealnie płaski)",
            ),
            kpi_card(
                "Zmiana r/r",
                yoy_text,
                "ostatni pełny rok vs poprzedni",
                value_color=yoy_color,
            ),
            kpi_card(
                "Udział OZE",
                ren_text,
                ren_subtitle,
                value_color=ren_color,
            ),
            kpi_card(
                "Pozycja handlowa",
                trade_label,
                f"Netto: {kpis['net_position_gwh']:+,.0f} GWh",
                value_color=trade_color,
            ),
        ])

    # --- Monthly load chart (with peak overlay) ---
    df_load = get_monthly_load_clean(country, start_date, end_date)

    fig_load = make_subplots(specs=[[{"secondary_y": True}]])

    fig_load.add_trace(
        go.Bar(
            x=df_load["year_month"],
            y=df_load["load_sum"],
            name="Obciążenie miesięczne (MWh)",
            marker_color="#3391ff",
            opacity=0.7,
        ),
        secondary_y=False,
    )

    fig_load.add_trace(
        go.Scatter(
            x=df_load["year_month"],
            y=df_load["load_peak"],
            mode="lines+markers",
            name="Szczyt zapotrzebowania (MW)",
            line=dict(color="#ff6b6b", width=2),
            marker=dict(size=4),
        ),
        secondary_y=True,
    )

    fig_load.update_layout(
        title=f"Obciążenie miesięczne — {country_name}",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_load.update_yaxes(title_text="Obciążenie miesięczne (MWh)", secondary_y=False)
    fig_load.update_yaxes(title_text="Szczyt zapotrzebowania (MW)", secondary_y=True)
    fig_load.update_xaxes(title_text="Miesiąc")

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
                    lambda v: "#00d4aa" if v >= 0 else "#ff6b6b"
                ),
                name="Przepływ netto",
            )
        )

        fig_flow.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        fig_flow.update_layout(
            title=f"Przepływy transgraniczne netto — {country_name}",
            xaxis_title="Miesiąc",
            yaxis_title="Import netto (+) / eksport (−)",
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
                name="Obciążenie roczne (TWh)",
                marker_color="#3391ff",
            ),
            secondary_y=False,
        )

        fig_annual.add_trace(
            go.Scatter(
                x=df_annual["year"],
                y=df_annual["peak_mw"],
                mode="lines+markers",
                name="Szczyt zapotrzebowania (MW)",
                line=dict(color="#ff6b6b", width=2),
            ),
            secondary_y=True,
        )

        fig_annual.update_layout(
            title=f"Obciążenie roczne i szczyt — {country_name}",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_annual.update_yaxes(title_text="Obciążenie roczne (TWh)", secondary_y=False)
        fig_annual.update_yaxes(title_text="Szczyt zapotrzebowania (MW)", secondary_y=True)
        fig_annual.update_xaxes(title_text="Rok")

        # Load factor chart
        fig_lf = px.line(
            df_annual,
            x="year",
            y="load_factor",
            markers=True,
            labels={"year": "Rok", "load_factor": "Wsp. obciążenia"},
            title=f"Trend współczynnika obciążenia — {country_name}",
        )
        fig_lf.update_yaxes(range=[0, 1], tickformat=".2f")
        fig_lf.add_hline(
            y=df_annual["load_factor"].mean(),
            line_dash="dot",
            line_color="rgba(255,255,255,0.4)",
            annotation_text=f"Średnia: {df_annual['load_factor'].mean():.3f}",
            annotation_position="top right",
            annotation_font_color="#ccc",
        )

    return kpi_children, fig_load, fig_flow, fig_annual, fig_lf
