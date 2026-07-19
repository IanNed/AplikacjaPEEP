from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.io as pio

# ====================================================================
# PLOTLY DARK TEMPLATE 
# ====================================================================

DARK_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e0e0e0", family="Segoe UI, sans-serif"),
        title=dict(font=dict(size=16, color="#ffffff")),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            zerolinecolor="rgba(255,255,255,0.15)",
            linecolor="rgba(255,255,255,0.2)",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            zerolinecolor="rgba(255,255,255,0.15)",
            linecolor="rgba(255,255,255,0.2)",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ccc"),
        ),
        colorway=[
            "#04c81e", "#3374ff", "#f65a5a", "#f7cf2e",
            "#66c97a", "#9f81fb", "#e86f19", "#09a8c4",
            "#da3b8a", "#78b61a",
        ],
        margin=dict(l=50, r=30, t=50, b=40),
    )
)

# Register as default
pio.templates["dark_energy"] = DARK_TEMPLATE
pio.templates.default = "dark_energy"

# ====================================================================
# CARD COMPONENTS
# ====================================================================

def chart_card(title: str, graph_id: str, height: str = "400px"):
    """Wrap a chart in a styled dark card."""
    return dbc.Card(
        [
            dbc.CardHeader(title, style={"fontWeight": "600", "fontSize": "0.95rem"}),
            dbc.CardBody(
                dcc.Graph(
                    id=graph_id,
                    style={"height": height},
                    config={"displayModeBar": False},
                ),
                style={"padding": "0.5rem"},
            ),
        ],
        className="mb-3",
        style={
            "backgroundColor": "#2d2d2d",
            "border": "1px solid #3d3d3d",
            "borderRadius": "10px",
        },
    )

def chart_card_figure(title: str, graph_id: str, height: str = "400px"):
    """Same as chart_card but returns graph component separately for custom layouts."""
    card = dbc.Card(
        [
            dbc.CardHeader(title, style={"fontWeight": "600", "fontSize": "0.95rem"}),
            dbc.CardBody(
                dcc.Graph(id=graph_id, style={"height": height}),
                style={"padding": "0.5rem"},
            ),
        ],
        className="mb-3",
        style={
            "backgroundColor": "#2d2d2d",
            "border": "1px solid #3d3d3d",
            "borderRadius": "10px",
        },
    )
    return card

def kpi_card(title: str, value: str, subtitle: str = "", value_color: str = "#00d4aa"):
    """Single KPI metric card for dark mode."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(title, style={
                    "fontSize": "0.75rem",
                    "color": "#999",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.5px",
                    "marginBottom": "4px",
                }),
                html.Div(value, style={
                    "fontSize": "1.5rem",
                    "fontWeight": "bold",
                    "color": value_color,
                }),
                html.Div(subtitle, style={
                    "fontSize": "0.7rem",
                    "color": "#666",
                    "marginTop": "4px",
                }),
            ],
            style={"padding": "1rem", "textAlign": "center"},
        ),
        style={
            "backgroundColor": "#2d2d2d",
            "border": "1px solid #3d3d3d",
            "borderRadius": "10px",
        },
        className="h-100",
    )

def kpi_row(cards: list):
    """Wrap multiple KPI cards in a responsive row."""
    cols = [dbc.Col(card, xs=6, sm=4, md=3, lg=2, className="mb-3") for card in cards]
    return dbc.Row(cols, className="g-3 mb-4")

# ====================================================================
# CONTROL PANEL
# ====================================================================

def control_panel(*children):
    """Wrap filter controls in a styled card."""
    return dbc.Card(
        dbc.CardBody(
            list(children),
            style={"padding": "1rem 1.5rem"},
        ),
        className="mb-4",
        style={
            "backgroundColor": "#2a2a2a",
            "border": "1px solid #3d3d3d",
            "borderRadius": "10px",
        },
    )

# ====================================================================
# PAGE HEADER
# ====================================================================

def page_header(title: str, description: str = ""):
    """Standard page header with title and optional description."""
    children = [
        html.H2(title, style={"color": "#fff", "marginBottom": "0.5rem"}),
    ]
    if description:
        children.append(
            html.P(description, style={"color": "#999", "marginBottom": "1.5rem", "fontSize": "0.9rem"})
        )
    return html.Div(children, className="mb-3")

# ====================================================================
# SECTION DIVIDER
# ====================================================================

def section_header(title: str, subtitle: str = ""):
    """Section title within a page."""
    children = [
        html.H4(title, style={"color": "#e0e0e0", "marginTop": "2rem", "marginBottom": "0.5rem"}),
    ]
    if subtitle:
        children.append(
            html.P(subtitle, style={"color": "#777", "fontSize": "0.85rem", "marginBottom": "1rem"})
        )
    return html.Div(children)

# ====================================================================
# DATA TABLE STYLING
# ====================================================================

DARK_TABLE_STYLE = {
    "style_table": {"overflowX": "auto"},
    "style_cell": {
        "textAlign": "center",
        "padding": "8px 12px",
        "backgroundColor": "#2d2d2d",
        "color": "#e0e0e0",
        "border": "1px solid #3d3d3d",
        "fontSize": "0.85rem",
    },
    "style_header": {
        "fontWeight": "bold",
        "backgroundColor": "#1a1a1a",
        "color": "#fff",
        "border": "1px solid #3d3d3d",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": "#333"},
    ],
}

# ====================================================================
# DROPDOWN STYLING (for dark mode)
# ====================================================================

DARK_DROPDOWN_STYLE = {
    "backgroundColor": "#2d2d2d",
    "color": "#e0e0e0",
}
