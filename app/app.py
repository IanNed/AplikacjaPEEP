import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP] if "dash_bootstrap_components" in globals() else None,
)

app.layout = html.Div(
    [
        html.Div(
            [
                dcc.Link("Home", href="/"),
                dcc.Link("Country overview", href="/country-overview", style={"marginLeft": "1rem"}),
                dcc.Link("Interconnectors", href="/interconnectors", style={"marginLeft": "1rem"}),
                dcc.Link("Seasonality decomposition", href="/seasonality", style={"marginLeft": "1rem"}),
                dcc.Link("Load patterns", href="/load-patterns", style={"marginLeft": "1rem"}),
                dcc.Link("Compare countries", href="/compare-countries", style={"marginLeft": "1rem"}),
                dcc.Link("Renewables capacity", href="/renewables-capacity", style={"marginLeft": "1rem"}),
                dcc.Link("Renewables vs load", href="/renewables-vs-load", style={"marginLeft": "1rem"}),
                dcc.Link("Compare renewables", href="/compare-renewables", style={"marginLeft": "1rem"}),
                dcc.Link("Energy transition pace", href="/energy-transition-pace", style={"marginLeft": "1rem"}),
                html.Li(dcc.Link("Self-sufficiency", href="/self-sufficiency")),],
            style={
                "padding": "0.5rem 1rem",
                "borderBottom": "1px solid #ccc",
                "backgroundColor": "#f8f8f8",
            },
        ),
        dash.page_container,
    ]
)

if __name__ == "__main__":
    app.run(debug=True)