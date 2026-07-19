import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    get_map_renewable_share,
    get_map_load_intensity,
    get_map_net_flows,
    get_map_self_sufficiency,
    get_map_year_bounds,
)

from app.components import (
    page_header, control_panel, section_header,
)

dash.register_page(
    __name__,
    path="/map",
    name="Mapa",
    title="Mapa energetyczna Europy",
)

# -----------------------------------------------------------------------
# Data setup
# -----------------------------------------------------------------------

MIN_YEAR, MAX_YEAR = get_map_year_bounds()

MAP_LAYERS = [
    {"label": "Udział OZE (%)", "value": "renewable_share"},
    {"label": "Roczne obciążenie (TWh)", "value": "load_intensity"},
    {"label": "Import/eksport netto (GWh)", "value": "net_flows"},
    {"label": "Wskaźnik samowystarczalności", "value": "self_sufficiency"},
    {"label": "Samowystarczalność OZE (%)", "value": "renewable_self_sufficiency"},
]

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Mapa energetyczna Europy",
        "Geoprzestrzenny przegląd europejskich systemów elektroenergetycznych. "
        "Wybierz metrykę i rok, aby zobaczyć porównanie krajów na mapie."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Metryka", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="map-layer",
                    options=MAP_LAYERS,
                    value="renewable_share",
                    clearable=False,
                ),
            ], md=6),
            dbc.Col([
                dbc.Label("Rok", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="map-year",
                    options=[{"label": str(y), "value": y} for y in range(MIN_YEAR, MAX_YEAR + 1)],
                    value=MAX_YEAR,
                    clearable=False,
                ),
            ], md=4),
        ]),
    ),

    # Main map
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(
                id="map-choropleth",
                style={"height": "620px"},
                config={"displayModeBar": False},
            ),
            style={"padding": "0.5rem"},
        ),
        className="mb-3",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),

    # Metric explanation
    html.Div(
        id="map-explanation",
        style={
            "marginTop": "1rem",
            "padding": "1rem",
            "backgroundColor": "#2a2a2a",
            "border": "1px solid #3d3d3d",
            "borderRadius": "8px",
            "fontSize": "0.9rem",
            "color": "#bbb",
        },
    ),
])

# -----------------------------------------------------------------------
# Callback
# -----------------------------------------------------------------------

@callback(
    Output("map-choropleth", "figure"),
    Output("map-explanation", "children"),
    Input("map-layer", "value"),
    Input("map-year", "value"),
)
def update_map(layer, year):
    empty_fig = go.Figure()

    if not layer or not year:
        return empty_fig, ""

    year = int(year)

    if layer == "renewable_share":
        df = get_map_renewable_share(year)
        if df.empty:
            return empty_fig, "Brak danych dla tego roku."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="renewable_share_pct",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "renewable_share_pct": ":.1f"},
            color_continuous_scale="YlGn",
            range_color=[0, 100],
            labels={"renewable_share_pct": "Udział OZE (%)"},
            title=f"Udział OZE w wytwarzaniu energii elektrycznej — {year}",
        )

        explanation = html.Div([
            html.Strong("Udział OZE: ", style={"color": "#00d4aa"}),
            "Procent całkowitego wytwarzania energii elektrycznej ze źródeł odnawialnych "
            "(hydro, wiatr, słońce, geotermia, biomasa). Dane: Eurostat. "
            "Ciemna zieleń = wysoki udział OZE. Jasny kolor = dominacja paliw kopalnych.",
        ])

    elif layer == "load_intensity":
        df = get_map_load_intensity(year)
        if df.empty:
            return empty_fig, "Brak danych dla tego roku."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="annual_load_twh",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "annual_load_twh": ":.1f"},
            color_continuous_scale="Reds",
            labels={"annual_load_twh": "Roczne obciążenie (TWh)"},
            title=f"Zapotrzebowanie na energię (roczne obciążenie) — {year}",
        )

        explanation = html.Div([
            html.Strong("Roczne obciążenie: ", style={"color": "#ff6b6b"}),
            "Całkowite zużycie energii elektrycznej w terawatogodzinach (TWh). "
            "Dane: ENTSO-E. Odzwierciedla wielkość gospodarki i poziom elektryfikacji. "
            "Dominują zazwyczaj Niemcy, Francja, Turcja i Wielka Brytania.",
        ])

    elif layer == "net_flows":
        df = get_map_net_flows(year)
        if df.empty:
            return empty_fig, "Brak danych dla tego roku."

        max_abs = max(abs(df["net_import_gwh"].min()), abs(df["net_import_gwh"].max()), 1)

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="net_import_gwh",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "net_import_gwh": ":.0f", "position": True},
            color_continuous_scale="RdBu_r",
            range_color=[-max_abs, max_abs],
            color_continuous_midpoint=0,
            labels={"net_import_gwh": "Import netto (GWh)", "position": "Pozycja"},
            title=f"Import / eksport netto energii elektrycznej — {year}",
        )

        explanation = html.Div([
            html.Strong("Przepływy netto: ", style={"color": "#3391ff"}),
            "Czerwony = importer netto (zależy od sąsiadów), Niebieski = eksporter netto (produkuje nadwyżkę). "
            "Dane: ENTSO-E. Pokazuje bilans wymiany energii i zależność od połączeń transgranicznych.",
        ])

    elif layer == "self_sufficiency":
        df = get_map_self_sufficiency(year)
        if df.empty:
            return empty_fig, "Brak danych dla tego roku."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="self_sufficiency_ratio",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "self_sufficiency_ratio": ":.2f"},
            color_continuous_scale="RdYlGn",
            range_color=[0.5, 1.5],
            color_continuous_midpoint=1.0,
            labels={"self_sufficiency_ratio": "Samowystarczalność (wytw./obciąż.)"},
            title=f"Wskaźnik samowystarczalności (wytwarzanie / obciążenie) — {year}",
        )

        explanation = html.Div([
            html.Strong("Samowystarczalność: ", style={"color": "#ffd93d"}),
            "Stosunek wytwarzania krajowego do krajowego obciążenia. "
            "Wartości > 1 (zieleń) = kraj wytwarza więcej niż zużywa. "
            "Wartości < 1 (czerwień) = zależy od importu. Łączy dane Eurostat + ENTSO-E.",
        ])

    elif layer == "renewable_self_sufficiency":
        df = get_map_self_sufficiency(year)
        if df.empty:
            return empty_fig, "Brak danych dla tego roku."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="renewable_self_sufficiency_pct",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "renewable_self_sufficiency_pct": ":.1f"},
            color_continuous_scale="Greens",
            range_color=[0, 100],
            labels={"renewable_self_sufficiency_pct": "Samowystarczalność OZE (%)"},
            title=f"Samowystarczalność OZE (wytwarzanie OZE / obciążenie) — {year}",
        )

        explanation = html.Div([
            html.Strong("Samowystarczalność OZE: ", style={"color": "#6bcf7f"}),
            "Jaki procent całkowitego zapotrzebowania na energię może być pokryty wyłącznie "
            "przez krajowe wytwarzanie odnawialne. 100% = całe zapotrzebowanie teoretycznie pokryte przez OZE. "
            "Syntetyczny wskaźnik postępu transformacji energetycznej.",
        ])

    else:
        return empty_fig, ""

    # Apply Europe-focused dark-mode view
    fig.update_geos(
        scope="europe",
        projection_type="natural earth",
        showcoastlines=True,
        coastlinecolor="#555",
        showland=True,
        landcolor="#1a1a1a",
        showocean=True,
        oceancolor="#111",
        showlakes=True,
        lakecolor="#111",
        showframe=False,
        resolution=50,
        lonaxis_range=[-12, 45],
        lataxis_range=[34, 72],
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0),
        geo=dict(bgcolor="rgba(0,0,0,0)"),
        coloraxis_colorbar=dict(
            thickness=15,
            len=0.7,
            yanchor="middle",
            y=0.5,
            tickfont=dict(color="#ccc"),
            title_font=dict(color="#ccc"),
        ),
    )

    return fig, explanation
