import dash
from dash import html, dcc

dash.register_page(
    __name__,
    path="/",
    name="Home",
    title="Energy EU Dashboard",
)

layout = html.Div(
    [
        html.H2("Energy EU Dashboard"),
        html.P("Select a view:"),
        html.Ul(
            [
                html.Li(dcc.Link("Country overview", href="/country-overview")),
                html.Li(dcc.Link("Load patterns", href="/load-patterns")),
                html.Li(dcc.Link("Seasonality decomposition", href="/seasonality")),
                html.Li(dcc.Link("Interconnectors", href="/interconnectors")),
                html.Li(dcc.Link("Compare countries", href="/compare-countries")),
                html.Li(dcc.Link("Renewables capacity", href="/renewables-capacity")),
                html.Li(dcc.Link("Renewables vs load", href="/renewables-vs-load")),
                html.Li(dcc.Link("Compare renewables", href="/compare-renewables")),
            ]
        ),
    ]
)