import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_share,
    get_generation_by_fuel,
    get_generation_year_bounds,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card, section_header,
)

dash.register_page(
    __name__,
    path="/renewables-capacity",
    name="Moc i wytwarzanie OZE",
    title="Moc i wytwarzanie OZE",
)

# Eurostat annual generation share dataset
_eu_df = load_eurostat_share_annual()
COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in sorted(_eu_df["country"].unique())
]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Wytwarzanie OZE w czasie",
        "Roczna wielkość i udział wytwarzania odnawialnego z danych Eurostat, z podziałem na technologie."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraj", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="rc-country",
                    options=COUNTRY_OPTIONS,
                    value="PL",
                    clearable=False,
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Zakres lat", style={"color": "#ccc"}),
                dcc.RangeSlider(
                    id="rc-year-range",
                    min=MIN_YEAR,
                    max=MAX_YEAR,
                    value=[MIN_YEAR, MAX_YEAR],
                    marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1, 2)},
                    allowCross=False,
                ),
            ], md=8),
        ]),
    ),

    # Charts
    dbc.Row([
        dbc.Col(chart_card("OZE a wytwarzanie całkowite", "rc-share-graph"), md=6),
        dbc.Col(chart_card("Wytwarzanie OZE wg technologii", "rc-tech-graph"), md=6),
    ]),
])

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

@callback(
    Output("rc-share-graph", "figure"),
    Output("rc-tech-graph", "figure"),
    Input("rc-country", "value"),
    Input("rc-year-range", "value"),
)
def update_renewables_generation(country, year_range):
    empty_fig = go.Figure()

    if not country or not year_range:
        return empty_fig, empty_fig

    country_name = COUNTRY_NAMES_PL.get(country, country)
    start_year, end_year = year_range

    # Annual renewable share and volumes from Eurostat
    df_share = get_generation_share(country)
    df_share = df_share[(df_share["year"] >= start_year) & (df_share["year"] <= end_year)].copy()

    if df_share.empty:
        return empty_fig, empty_fig

    # Chart 1: renewable generation bar + share line (dual axis)
    fig_share_bar = px.bar(
        df_share,
        x="year",
        y="renewable_generation_gwh",
        labels={
            "year": "Rok",
            "renewable_generation_gwh": "Wytwarzanie OZE (GWh)",
        },
        title=f"Wytwarzanie OZE i udział — {country_name}",
    )
    fig_share_bar.update_traces(marker_color="#00d4aa")

    fig_share_line = px.line(
        df_share,
        x="year",
        y="renewable_share",
    )
    fig_share_line.update_traces(yaxis="y2", name="Udział OZE", line=dict(color="#ffd93d", width=2.5))
    fig_share_bar.add_traces(fig_share_line.data)

    fig_share_bar.update_layout(
        yaxis=dict(title="Wytwarzanie OZE (GWh)"),
        yaxis2=dict(
            title="Udział",
            overlaying="y",
            side="right",
            tickformat=".0%",
            range=[0, 1],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Chart 2: renewable generation by fuel/technology
    df_fuel = get_generation_by_fuel(country)
    df_fuel = df_fuel[(df_fuel["year"] >= start_year) & (df_fuel["year"] <= end_year)].copy()

    # Map fuel labels to Polish
    fuel_map_pl = {
        "Hydro total": "Hydro",
        "Wind total": "Wiatr",
        "Solar total": "Słońce",
        "Geothermal": "Geotermia",
        "Other renewables": "Inne OZE",
        "Renewables & biofuels (aggregate)": "OZE i biopaliwa (łącznie)",
    }
    df_fuel["fuel_pl"] = df_fuel["fuel"].map(fuel_map_pl).fillna(df_fuel["fuel"])

    fig_fuel = px.bar(
        df_fuel,
        x="year",
        y="generation_gwh",
        color="fuel_pl",
        labels={
            "year": "Rok",
            "generation_gwh": "Wytwarzanie (GWh)",
            "fuel_pl": "Technologia",
        },
        title=f"Wytwarzanie OZE wg technologii — {country_name}",
        color_discrete_map={
            "Hydro": "#06b6d4",
            "Wiatr": "#6bcf7f",
            "Słońce": "#ffd93d",
            "Geotermia": "#f97316",
            "Inne OZE": "#a78bfa",
            "OZE i biopaliwa (łącznie)": "#00d4aa",
        },
    )

    return fig_share_bar, fig_fuel
