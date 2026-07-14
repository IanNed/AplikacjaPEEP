import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_daily,
    get_daily_load_with_daytype,
    get_intraday_profile,
    get_day_of_week_profile,
    get_load_statistics,
    get_monthly_load_heatmap_data,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card, kpi_card, kpi_row,
    section_header,
)

dash.register_page(
    __name__,
    path="/load-patterns",
    name="Wzorce obciążeń",
    title="Wzorce obciążeń",
)

_daily_df = load_daily()

COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_daily_df["country"].unique())
]

MIN_DATE = _daily_df["date"].min()
MAX_DATE = _daily_df["date"].max()

DEFAULT_END = MAX_DATE
DEFAULT_START = MAX_DATE - pd.Timedelta(days=90)

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Wzorce obciążeń",
        "Analiza dziennych i dobowych wzorców zapotrzebowania na energię elektryczną, "
        "w tym różnice między dniami roboczymi a weekendami, profile tygodniowe i mapy sezonowe."
    ),

    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraj", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="lp-country",
                    options=COUNTRY_OPTIONS,
                    value="PL",
                    clearable=False,
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Okno analizy", style={"color": "#ccc"}),
                dcc.DatePickerRange(
                    id="lp-date-range",
                    min_date_allowed=MIN_DATE,
                    max_date_allowed=MAX_DATE,
                    start_date=DEFAULT_START,
                    end_date=DEFAULT_END,
                    display_format="YYYY-MM-DD",
                ),
            ], md=8),
        ]),
    ),

    html.Div(id="lp-stats", className="mb-4"),

    dbc.Row([
        dbc.Col(chart_card("Obciążenie dzienne (kolor wg typu dnia)", "lp-daily-graph"), md=6),
        dbc.Col(chart_card("Profil dobowy (średnia godzinowa)", "lp-intraday-graph"), md=6),
    ]),

    dbc.Row([
        dbc.Col(chart_card("Średnie obciążenie wg dnia tygodnia", "lp-dow-graph"), md=6),
        dbc.Col(chart_card("Rozkład: dzień roboczy vs weekend", "lp-box-graph"), md=6),
    ]),

    section_header(
        "Mapa cieplna sezonowości",
        "Średnie dzienne obciążenie wg miesiąca i roku dla całego zakresu danych."
    ),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="lp-heatmap-graph", style={"height": "350px"}),
            style={"padding": "0.5rem"},
        ),
        className="mb-3",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),
])

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

@callback(
    Output("lp-stats", "children"),
    Output("lp-daily-graph", "figure"),
    Output("lp-intraday-graph", "figure"),
    Output("lp-dow-graph", "figure"),
    Output("lp-box-graph", "figure"),
    Output("lp-heatmap-graph", "figure"),
    Input("lp-country", "value"),
    Input("lp-date-range", "start_date"),
    Input("lp-date-range", "end_date"),
)
def update_load_patterns(country, start_date, end_date):
    empty_fig = go.Figure()

    if not country or not start_date or not end_date:
        return html.Div(), empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    country_name = COUNTRY_NAMES_PL.get(country, country)

    # --- Statistics cards ---
    stats = get_load_statistics(country, start_date, end_date)

    if not stats:
        stats_children = html.Div("Brak danych w wybranym oknie.", style={"color": "#ff6b6b", "padding": "1rem"})
    else:
        stats_children = kpi_row([
            kpi_card("Okres", f"{stats['total_days']} dni", f"{stats['total_load_gwh']} GWh łącznie"),
            kpi_card("Śr. dzienne obciążenie", f"{stats['avg_daily_load_mwh']:,.0f} MWh", f"CV: {stats['coeff_variation']:.3f}"),
            kpi_card(
                "Szczyt zapotrzebowania",
                f"{stats['peak_load_mw']:,.0f} MW",
                f"{stats['peak_date'].strftime('%Y-%m-%d')}",
                value_color="#ff6b6b",
            ),
            kpi_card(
                "Minimum zapotrzebowania",
                f"{stats['min_load_mw']:,.0f} MW",
                f"{stats['min_date'].strftime('%Y-%m-%d')}",
                value_color="#3391ff",
            ),
            kpi_card("Wsp. obciążenia", f"{stats['load_factor']:.3f}", "śr. / szczyt (wyższy = bardziej płaski)"),
            kpi_card(
                "Spadek weekendowy",
                f"{stats['weekend_drop_pct']:.1f}%",
                f"DR: {stats['weekday_avg_mwh']:,.0f} → WE: {stats['weekend_avg_mwh']:,.0f}",
                value_color="#f97316",
            ),
        ])

    # --- Daily load chart ---
    df_daily = get_daily_load_with_daytype(country, start_date, end_date)

    if df_daily.empty:
        fig_daily = empty_fig
    else:
        df_daily = df_daily.copy()
        df_daily["typ_dnia"] = df_daily["day_type"].map({"Weekday": "Dzień roboczy", "Weekend": "Weekend"})

        fig_daily = px.scatter(
            df_daily,
            x="date",
            y="load_sum",
            color="typ_dnia",
            color_discrete_map={"Dzień roboczy": "#3391ff", "Weekend": "#f97316"},
            labels={"date": "Data", "load_sum": "Obciążenie dzienne (MWh)", "typ_dnia": "Typ dnia"},
            title=f"Obciążenie dzienne — {country_name}",
        )
        fig_daily.update_traces(marker=dict(size=5))

        fig_daily.add_trace(
            go.Scatter(
                x=df_daily["date"],
                y=df_daily["load_sum"].rolling(7, center=True, min_periods=1).mean(),
                mode="lines",
                name="Śr. 7-dniowa",
                line=dict(color="#e0e0e0", width=2, dash="solid"),
                opacity=0.7,
            )
        )

    # --- Intraday profile (only for windows ≤ 30 days) ---
    date_diff = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
    if date_diff <= 30:
        df_profile = get_intraday_profile(country, start_date, end_date)
    else:
        df_profile = pd.DataFrame()

    if df_profile.empty:
        fig_intraday = go.Figure()
        fig_intraday.update_layout(title="Wybierz okno ≤ 30 dni aby zobaczyć profil dobowy")
    else:
        fig_intraday = go.Figure()

        fig_intraday.add_trace(
            go.Scatter(
                x=df_profile["hour"],
                y=df_profile["load_mean"],
                mode="lines+markers",
                name="Średnie obciążenie",
                line=dict(color="#3391ff", width=2),
                fill="tozeroy",
                fillcolor="rgba(51,145,255,0.1)",
            )
        )

        fig_intraday.add_trace(
            go.Scatter(
                x=df_profile["hour"],
                y=df_profile["load_peak"],
                mode="lines+markers",
                name="Szczyt obciążenia",
                line=dict(color="#ff6b6b", width=1.5, dash="dash"),
            )
        )

        fig_intraday.update_layout(
            title=f"Profil dobowy — {country_name}",
            xaxis_title="Godzina",
            yaxis_title="Obciążenie (MW)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

    # --- Day-of-week profile ---
    df_dow = get_day_of_week_profile(country, start_date, end_date)

    if df_dow.empty:
        fig_dow = empty_fig
    else:
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_names_pl = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Ndz"]

        df_dow["day_name"] = pd.Categorical(df_dow["day_name"], categories=day_order, ordered=True)
        df_dow = df_dow.sort_values("day_name")
        df_dow["dzien"] = day_names_pl

        colors = ["#3391ff"] * 5 + ["#f97316"] * 2

        fig_dow = go.Figure()

        fig_dow.add_trace(
            go.Bar(
                x=df_dow["dzien"],
                y=df_dow["avg_load_sum"],
                marker_color=colors,
                error_y=dict(type="data", array=df_dow["std_load_sum"], visible=True, color="#666"),
                name="Śr. obciążenie dzienne",
            )
        )

        fig_dow.update_layout(
            title=f"Średnie obciążenie wg dnia — {country_name}",
            xaxis_title="Dzień tygodnia",
            yaxis_title="Śr. obciążenie dzienne (MWh)",
            showlegend=False,
        )

    # --- Weekday vs Weekend box plot ---
    if df_daily.empty:
        fig_box = empty_fig
    else:
        fig_box = px.box(
            df_daily,
            x="typ_dnia",
            y="load_sum",
            color="typ_dnia",
            color_discrete_map={"Dzień roboczy": "#3391ff", "Weekend": "#f97316"},
            points="outliers",
            labels={"typ_dnia": "Typ dnia", "load_sum": "Obciążenie dzienne (MWh)"},
            title=f"Rozkład obciążenia wg typu dnia — {country_name}",
        )
        fig_box.update_layout(showlegend=False)

    # --- Seasonal heatmap ---
    df_heatmap = get_monthly_load_heatmap_data(country, MIN_DATE, MAX_DATE)

    if df_heatmap.empty:
        fig_heatmap = empty_fig
    else:
        pivot = df_heatmap.pivot(index="year", columns="month", values="avg_daily_load")

        month_labels = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze",
                        "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]

        fig_heatmap = px.imshow(
            pivot.values,
            x=month_labels,
            y=[str(y) for y in pivot.index],
            color_continuous_scale="Inferno",
            aspect="auto",
            labels={"color": "Śr. dzienne obciążenie (MWh)", "x": "Miesiąc", "y": "Rok"},
            title=f"Mapa cieplna sezonowości — {country_name} (cały zakres)",
        )
        fig_heatmap.update_layout(height=350)

    return stats_children, fig_daily, fig_intraday, fig_dow, fig_box, fig_heatmap
