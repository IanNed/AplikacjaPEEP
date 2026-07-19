import sys
import os
import dash

#pre-imported libs
import sklearn.cluster
import sklearn.preprocessing
import sklearn.decomposition

from dash import html, dcc
import dash_bootstrap_components as dbc

# Handle paths for PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    PAGES_FOLDER = os.path.join(BASE_DIR, "app", "pages")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PAGES_FOLDER = os.path.join(BASE_DIR, "pages")

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=PAGES_FOLDER,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css",
    ],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# --- Navbar ---
navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand(
                "Energy EU",
                href="/",
                style={"fontWeight": "bold", "fontSize": "1.2rem"},
            ),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavItem(dbc.NavLink("Przegląd kraju", href="/country-overview")),
                        dbc.NavItem(dbc.NavLink("Wzorce obciążeń", href="/load-patterns")),
                        dbc.NavItem(dbc.NavLink("Sezonowość", href="/seasonality")),
                        dbc.NavItem(dbc.NavLink("Połączenia (import/eksport)", href="/interconnectors")),
                        dbc.NavItem(dbc.NavLink("Porównanie krajów", href="/compare-countries")),
                        dbc.DropdownMenu(
                            label="OZE",
                            nav=True,
                            children=[
                                dbc.DropdownMenuItem("Moc i generacja", href="/renewables-capacity"),
                                dbc.DropdownMenuItem("OZE vs obciążenie", href="/renewables-vs-load"),
                                dbc.DropdownMenuItem("Porównanie OZE między krajami", href="/compare-renewables"),
                                dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem("Tempo transformacji", href="/energy-transition-pace"),
                                dbc.DropdownMenuItem("Samowystarczalność", href="/self-sufficiency"),
                            ],
                        ),
                        dbc.DropdownMenu(
                            label="Zaawansowane",
                            nav=True,
                            children=[
                                dbc.DropdownMenuItem("Mapa", href="/map"),
                                dbc.DropdownMenuItem("Grupowanie", href="/clustering"),
                            ],
                        ),
                    ],
                    navbar=True,
                ),
                id="navbar-collapse",
                navbar=True,
            ),
        ],
        fluid=True,
    ),
    color="dark",
    dark=True,
    sticky="top",
    style={"marginBottom": "1.5rem"},
)

# --- Main layout ---
app.layout = html.Div(
    [
        navbar,
        dbc.Container(
            dash.page_container,
            fluid=True,
            style={"paddingBottom": "2rem"},
            className="dbc",
        ),
    ],
    style={"backgroundColor": "#222", "minHeight": "100vh"},
    className="dbc",
)

if __name__ == "__main__":
    from flaskwebgui import FlaskUI
    FlaskUI(
        app=app.server,
        server="flask",
        width=1400,
        height=900,
        port=8050,
    ).run()
