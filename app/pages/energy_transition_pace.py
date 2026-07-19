import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_share,
    get_generation_year_bounds,
    compute_yoy_growth,
    get_transition_scorecard,
    get_tech_growth,
    get_transition_acceleration,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/energy-transition-pace",
    name="Tempo transformacji",
    title="Tempo transformacji energetycznej",
)

# -----------------------------------------------------------------------
# Data setup
# -----------------------------------------------------------------------

_eu_df = load_eurostat_share_annual()

COUNTRIES = sorted(_eu_df["country"].unique())
COUNTRY_OPTIONS = [
    {"label": COUNTRY_NAMES_PL.get(c, c), "value": c}
    for c in COUNTRIES
]

MIN_YEAR, MAX_YEAR = get_generation_year_bounds()

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Tempo transformacji energetycznej",
        "Mierzy, jak szybko kraje zwiększają generację odnawialną. "
        "Wykorzystuje wskaźniki rok-do-roku (r/r) i średnioroczne tempo wzrostu (CAGR) "
        "do rankingowania krajów i porównywania postępów technologicznych."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraje (wybierz dla widoku szczegółowego)", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="etp-countries",
                    options=COUNTRY_OPTIONS,
                    value=["PL", "DE", "ES", "FR", "IT"],
                    multi=True,
                    clearable=False,
                ),
            ], md=7),
            dbc.Col([
                dbc.Label("Zakres lat", style={"color": "#ccc"}),
                dcc.RangeSlider(
                    id="etp-year-range",
                    min=MIN_YEAR,
                    max=MAX_YEAR,
                    value=[MIN_YEAR, MAX_YEAR],
                    marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                    allowCross=False,
                ),
            ], md=5),
        ]),
    ),

    # Section 1: Transition Scorecard
    section_header(
        "Karta wyników transformacji",
        "Wszystkie kraje uszeregowane wg poprawy udziału OZE (pp przyrostu). "
        "CAGR mierzy wygładzone roczne tempo wzrostu wolumenu generacji odnawialnej."
    ),
    dash_table.DataTable(
        id="etp-scorecard-table",
        columns=[],
        data=[],
        page_size=15,
        sort_action="native",
        filter_action="native",
        style_table=DARK_TABLE_STYLE["style_table"],
        style_cell=DARK_TABLE_STYLE["style_cell"],
        style_header=DARK_TABLE_STYLE["style_header"],
        style_data_conditional=[
            *DARK_TABLE_STYLE["style_data_conditional"],
            {"if": {"filter_query": "{share_change_pp} > 10"}, "backgroundColor": "#1a3a2a", "color": "#6bcf7f"},
            {"if": {"filter_query": "{share_change_pp} < 0"}, "backgroundColor": "#3a1a1a", "color": "#ff6b6b"},
            {"if": {"column_id": "rank", "filter_query": "{rank} <= 3"}, "fontWeight": "bold", "color": "#00d4aa"},
        ],
    ),

    # Section 2: YoY Growth Charts
    section_header("Wzrost generacji OZE rok do roku"),
    dbc.Row([
        dbc.Col(chart_card("Tempo wzrostu r/r (%)", "etp-yoy-graph"), md=6),
        dbc.Col(chart_card("Przebieg udziału OZE", "etp-share-trajectory-graph"), md=6),
    ]),

    # Section 3: Technology breakdown
    section_header(
        "Wzrost wg technologii (CAGR %)",
        "Które technologie napędzają transformację? Porównanie średniorocznego tempa wzrostu "
        "hydro, wiatru, słońca, geotermii i innych OZE."
    ),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="etp-tech-graph", style={"height": "400px"}),
            style={"padding": "0.5rem"},
        ),
        className="mb-4",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),

    # Section 4: Acceleration indicator
    section_header(
        "Przyspieszenie vs spowolnienie",
        "Czy transformacja przyspiesza, czy zwalnia? Porównanie średniego wzrostu r/r "
        "w pierwszej połowie okresu vs drugiej połowie."
    ),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="etp-acceleration-graph", style={"height": "400px"}),
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
    Output("etp-scorecard-table", "data"),
    Output("etp-scorecard-table", "columns"),
    Output("etp-yoy-graph", "figure"),
    Output("etp-share-trajectory-graph", "figure"),
    Output("etp-tech-graph", "figure"),
    Output("etp-acceleration-graph", "figure"),
    Input("etp-countries", "value"),
    Input("etp-year-range", "value"),
)
def update_transition_pace(countries, year_range):
    empty_fig = go.Figure()

    if not countries or not year_range:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    # --- Scorecard (ALL countries) ---
    scorecard = get_transition_scorecard(COUNTRIES, start_year, end_year)

    if scorecard.empty:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    # Map country names
    scorecard = scorecard.copy()
    scorecard["kraj"] = scorecard["country"].map(COUNTRY_NAMES_PL)

    scorecard_columns = [
        {"name": "#", "id": "rank"},
        {"name": "Kraj", "id": "kraj"},
        {"name": f"Udział {start_year} (%)", "id": "start_share_pct"},
        {"name": f"Udział {end_year} (%)", "id": "end_share_pct"},
        {"name": "Zmiana (pp)", "id": "share_change_pp"},
        {"name": "CAGR (%)", "id": "cagr_pct"},
        {"name": "Śr. r/r (%)", "id": "avg_yoy_growth_pct"},
    ]
    scorecard_data = scorecard.to_dict("records")

    # --- YoY growth chart (selected countries) ---
    yoy_frames = []
    for country in countries:
        df_yoy = compute_yoy_growth(country, start_year, end_year)
        if df_yoy.empty:
            continue
        df_yoy = df_yoy.dropna(subset=["yoy_growth_pct"])
        df_yoy["country_name"] = COUNTRY_NAMES_PL.get(country, country)
        yoy_frames.append(df_yoy)

    if yoy_frames:
        df_yoy_all = pd.concat(yoy_frames, ignore_index=True)

        fig_yoy = px.line(
            df_yoy_all,
            x="year",
            y="yoy_growth_pct",
            color="country_name",
            markers=True,
            labels={
                "year": "Rok",
                "yoy_growth_pct": "Wzrost r/r (%)",
                "country_name": "Kraj",
            },
            title="Generacja OZE — wzrost rok do roku",
        )
        fig_yoy.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    else:
        fig_yoy = empty_fig

    # --- Renewable share trajectory (selected countries) ---
    share_frames = []
    for country in countries:
        df_c = get_generation_share(country)
        if df_c.empty:
            continue
        df_c = df_c[(df_c["year"] >= start_year) & (df_c["year"] <= end_year)].copy()
        df_c = df_c.dropna(subset=["renewable_share"])
        df_c["country_name"] = COUNTRY_NAMES_PL.get(country, country)
        share_frames.append(df_c)

    if share_frames:
        df_share_all = pd.concat(share_frames, ignore_index=True)

        fig_share = px.line(
            df_share_all,
            x="year",
            y="renewable_share",
            color="country_name",
            markers=True,
            labels={
                "year": "Rok",
                "renewable_share": "Udział OZE",
                "country_name": "Kraj",
            },
            title="Udział OZE w generacji całkowitej w czasie",
        )
        fig_share.update_yaxes(tickformat=".0%", range=[0, 1])
    else:
        fig_share = empty_fig

    # --- Technology growth (CAGR by tech) ---
    df_tech = get_tech_growth(countries, start_year, end_year)

    if not df_tech.empty:
        df_tech_valid = df_tech.dropna(subset=["cagr_pct"]).copy()
        df_tech_valid["country_name"] = df_tech_valid["country"].map(COUNTRY_NAMES_PL)

        tech_map_pl = {
            "Hydro": "Hydro", "Wind": "Wiatr", "Solar": "Słońce",
            "Geothermal": "Geotermia", "Other renewables": "Inne OZE",
        }
        df_tech_valid["tech_pl"] = df_tech_valid["technology"].map(tech_map_pl).fillna(df_tech_valid["technology"])

        fig_tech = px.bar(
            df_tech_valid,
            x="country_name",
            y="cagr_pct",
            color="tech_pl",
            barmode="group",
            labels={
                "country_name": "Kraj",
                "cagr_pct": "CAGR (%)",
                "tech_pl": "Technologia",
            },
            title="Średnioroczne tempo wzrostu wg technologii",
            color_discrete_map={
                "Hydro": "#06b6d4",
                "Wiatr": "#6bcf7f",
                "Słońce": "#ffd93d",
                "Geotermia": "#f97316",
                "Inne OZE": "#a78bfa",
            },
        )
    else:
        fig_tech = empty_fig

    # --- Acceleration chart ---
    df_accel = get_transition_acceleration(countries, start_year, end_year)

    if not df_accel.empty:
        df_accel = df_accel.copy()
        df_accel["country_name"] = df_accel["country"].map(COUNTRY_NAMES_PL)

        fig_accel = make_subplots(specs=[[{"secondary_y": False}]])

        fig_accel.add_trace(
            go.Bar(
                x=df_accel["country_name"],
                y=df_accel["first_half_avg_yoy"],
                name="1. połowa — śr. r/r",
                marker_color="#3391ff",
                opacity=0.6,
            )
        )
        fig_accel.add_trace(
            go.Bar(
                x=df_accel["country_name"],
                y=df_accel["second_half_avg_yoy"],
                name="2. połowa — śr. r/r",
                marker_color="#3391ff",
            )
        )
        fig_accel.add_trace(
            go.Scatter(
                x=df_accel["country_name"],
                y=df_accel["acceleration"],
                mode="markers+text",
                name="Przyspieszenie (pp)",
                marker=dict(
                    size=14,
                    color=df_accel["acceleration"].apply(
                        lambda v: "#00d4aa" if v > 0 else "#ff6b6b"
                    ),
                    symbol="diamond",
                ),
                text=df_accel["acceleration"].apply(lambda v: f"{v:+.1f}"),
                textposition="top center",
                textfont=dict(color="#ccc"),
            )
        )

        fig_accel.update_layout(
            barmode="group",
            title="Czy transformacja przyspiesza? (2. połowa vs 1. połowa okresu)",
            xaxis_title="Kraj",
            yaxis_title="Śr. wzrost r/r (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
    else:
        fig_accel = empty_fig

    return scorecard_data, scorecard_columns, fig_yoy, fig_share, fig_tech, fig_accel
