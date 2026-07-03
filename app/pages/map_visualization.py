import dash
from dash import html, dcc, callback, Input, Output
import plotly.express as px
import plotly.graph_objects as go

from app.backend.data_access import (
    get_map_renewable_share,
    get_map_load_intensity,
    get_map_net_flows,
    get_map_self_sufficiency,
    get_map_year_bounds,
)

dash.register_page(
    __name__,
    path="/map",
    name="Map",
    title="European energy map",
)

# -----------------------------------------------------------------------
# Data setup
# -----------------------------------------------------------------------

MIN_YEAR, MAX_YEAR = get_map_year_bounds()

MAP_LAYERS = [
    {"label": "Renewable share (%)", "value": "renewable_share"},
    {"label": "Annual load (TWh)", "value": "load_intensity"},
    {"label": "Net import/export (GWh)", "value": "net_flows"},
    {"label": "Self-sufficiency ratio", "value": "self_sufficiency"},
    {"label": "Renewable self-sufficiency (%)", "value": "renewable_self_sufficiency"},
]

# Europe center coordinates
EUROPE_CENTER = {"lat": 54, "lon": 15}

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div(
    [
        html.H2("European Energy Map"),
        html.P(
            "Geospatial overview of European electricity systems. Select a metric "
            "and year to see how countries compare on a map.",
            style={"color": "#555", "marginBottom": "1.5rem"},
        ),

        # Controls
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Metric"),
                        dcc.Dropdown(
                            id="map-layer",
                            options=MAP_LAYERS,
                            value="renewable_share",
                            clearable=False,
                        ),
                    ],
                    style={"width": "35%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.Label("Year"),
                        dcc.Slider(
                            id="map-year",
                            min=MIN_YEAR,
                            max=MAX_YEAR,
                            value=MAX_YEAR,
                            marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                            step=1,
                        ),
                    ],
                    style={"width": "60%", "display": "inline-block", "paddingLeft": "2rem"},
                ),
            ],
            style={"marginBottom": "1.5rem"},
        ),

        # Main map
        dcc.Graph(
            id="map-choropleth",
            style={"height": "620px"},
        ),

        # Metric explanation
        html.Div(
            id="map-explanation",
            style={"marginTop": "1rem", "padding": "1rem", "backgroundColor": "#f9f9f9",
                   "borderRadius": "8px", "fontSize": "0.9rem", "color": "#555"},
        ),
    ]
)

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
            return empty_fig, "No data available for this year."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="renewable_share_pct",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "renewable_share_pct": ":.1f"},
            color_continuous_scale="YlGn",
            range_color=[0, 100],
            labels={"renewable_share_pct": "Renewable share (%)"},
            title=f"Renewable Share of Electricity Generation — {year}",
        )

        explanation = html.Div([
            html.Strong("Renewable share: "),
            "Percentage of total electricity generation from renewable sources "
            "(hydro, wind, solar, geothermal, biomass). Data: Eurostat. "
            "Dark green = high renewable penetration. Light = fossil-dominated.",
        ])

    elif layer == "load_intensity":
        df = get_map_load_intensity(year)
        if df.empty:
            return empty_fig, "No data available for this year."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="annual_load_twh",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "annual_load_twh": ":.1f"},
            color_continuous_scale="Reds",
            labels={"annual_load_twh": "Annual load (TWh)"},
            title=f"Electricity Demand (Total Annual Load) — {year}",
        )

        explanation = html.Div([
            html.Strong("Annual load: "),
            "Total electricity consumption in Terawatt-hours (TWh). "
            "Data: ENTSO-E. Reflects economic size and electrification level. "
            "Germany, France, Turkey, and UK typically dominate.",
        ])

    elif layer == "net_flows":
        df = get_map_net_flows(year)
        if df.empty:
            return empty_fig, "No data available for this year."

        # Diverging scale: negative (exporter) = blue, positive (importer) = red
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
            labels={"net_import_gwh": "Net imports (GWh)", "position": "Position"},
            title=f"Net Electricity Imports / Exports — {year}",
        )

        explanation = html.Div([
            html.Strong("Net flows: "),
            "Red = net importer (relies on neighbours), Blue = net exporter (produces surplus). "
            "Data: ENTSO-E cross-border flows. Shows energy trade balance and interconnection dependency.",
        ])

    elif layer == "self_sufficiency":
        df = get_map_self_sufficiency(year)
        if df.empty:
            return empty_fig, "No data available for this year."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="self_sufficiency_ratio",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "self_sufficiency_ratio": ":.2f"},
            color_continuous_scale="RdYlGn",
            range_color=[0.5, 1.5],
            color_continuous_midpoint=1.0,
            labels={"self_sufficiency_ratio": "Self-sufficiency (gen/load)"},
            title=f"Self-Sufficiency Ratio (Generation / Load) — {year}",
        )

        explanation = html.Div([
            html.Strong("Self-sufficiency: "),
            "Ratio of domestic generation to domestic load. "
            "Values > 1 (green) = country generates more than it consumes. "
            "Values < 1 (red) = depends on imports. Combines Eurostat generation + ENTSO-E load.",
        ])

    elif layer == "renewable_self_sufficiency":
        df = get_map_self_sufficiency(year)
        if df.empty:
            return empty_fig, "No data available for this year."

        fig = px.choropleth(
            df,
            locations="iso_alpha3",
            color="renewable_self_sufficiency_pct",
            hover_name="country_name",
            hover_data={"iso_alpha3": False, "renewable_self_sufficiency_pct": ":.1f"},
            color_continuous_scale="Greens",
            range_color=[0, 100],
            labels={"renewable_self_sufficiency_pct": "Renewable self-suff. (%)"},
            title=f"Renewable Self-Sufficiency (Renewable Gen / Load) — {year}",
        )

        explanation = html.Div([
            html.Strong("Renewable self-sufficiency: "),
            "What percentage of total electricity demand can be covered by domestic "
            "renewable generation alone. 100% = all demand theoretically met by renewables. "
            "The ultimate measure of energy transition progress.",
        ])

    else:
        return empty_fig, ""

    # Apply Europe-focused view to all maps
    fig.update_geos(
        scope="europe",
        projection_type="natural earth",
        showcoastlines=True,
        coastlinecolor="gray",
        showland=True,
        landcolor="#f5f5f5",
        showocean=True,
        oceancolor="#e8f4fd",
        showlakes=True,
        lakecolor="#e8f4fd",
        showframe=False,
        resolution=50,
        lonaxis_range=[-12, 45],
        lataxis_range=[34, 72],
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0),
        coloraxis_colorbar=dict(
            thickness=15,
            len=0.7,
            yanchor="middle",
            y=0.5,
        ),
    )

    return fig, explanation
