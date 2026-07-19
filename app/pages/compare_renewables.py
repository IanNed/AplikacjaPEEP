import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    load_eurostat_share_annual,
    get_generation_year_bounds,
    get_renewable_share_comparison,
    get_technology_mix_comparison,
    get_renewable_growth_comparison,
    get_renewable_gap_to_target,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/compare-renewables",
    name="Porównanie OZE",
    title="Porównanie OZE",
)

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
        "Porównanie generacji OZE",
        "Porównanie wielu krajów pod kątem postępu w energetyce odnawialnej — zmiany udziałów, "
        "struktura źródeł, tempo wzrostu i dystans do celów."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraje", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="cr-countries",
                    options=COUNTRY_OPTIONS,
                    value=["DE", "PL", "ES", "FR", "SE"],
                    multi=True,
                    clearable=False,
                ),
            ], md=7),
            dbc.Col([
                dbc.Label("Zakres lat", style={"color": "#ccc"}),
                dcc.RangeSlider(
                    id="cr-year-range",
                    min=MIN_YEAR,
                    max=MAX_YEAR,
                    value=[MIN_YEAR, MAX_YEAR],
                    marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                    allowCross=False,
                ),
            ], md=5),
        ]),
    ),

    # Section 1: Share trajectories
    section_header("Zmiany udziału OZE w czasie"),
    chart_card("Udział OZE w generacji w czasie", "cr-share-graph"),

    # Growth summary table (below chart, full width)
    dbc.Card(
        [
            dbc.CardHeader("Podsumowanie wzrostu", style={"fontWeight": "600", "fontSize": "0.95rem"}),
            dbc.CardBody(
                dash_table.DataTable(
                    id="cr-growth-table",
                    columns=[],
                    data=[],
                    sort_action="native",
                    style_table=DARK_TABLE_STYLE["style_table"],
                    style_cell=DARK_TABLE_STYLE["style_cell"],
                    style_header=DARK_TABLE_STYLE["style_header"],
                    style_data_conditional=[
                        *DARK_TABLE_STYLE["style_data_conditional"],
                        {"if": {"filter_query": "{share_gain_pp} > 15"}, "backgroundColor": "#1a3a2a", "color": "#6bcf7f"},
                        {"if": {"filter_query": "{share_gain_pp} < 0"}, "backgroundColor": "#3a1a1a", "color": "#ff6b6b"},
                    ],
                ),
                style={"padding": "0.5rem"},
            ),
        ],
        className="mb-4",
        style={"backgroundColor": "#2d2d2d", "border": "1px solid #3d3d3d", "borderRadius": "10px"},
    ),

    # Section 2: Technology mix
    section_header("Struktura źródeł OZE (ostatni rok)"),
    dbc.Row([
        dbc.Col(chart_card("Generacja OZE wg źródła (GWh)", "cr-tech-abs-graph"), md=6),
        dbc.Col(chart_card("Udział poszczególnych źródeł w OZE (%)", "cr-tech-pct-graph"), md=6),
    ]),

    # Section 3: Growth race
    section_header("Porównanie tempa wzrostu"),
    dbc.Row([
        dbc.Col(chart_card("Bezwzględny wzrost generacji OZE (GWh)", "cr-growth-abs-graph"), md=6),
        dbc.Col(chart_card("Porównanie CAGR (%)", "cr-cagr-graph"), md=6),
    ]),

    # Section 4: Gap to target
    section_header(
        "Dystans do celu",
        "Jak daleko każdy kraj jest od docelowego udziału OZE? "
        "Pokazuje dodatkową generację (GWh) potrzebną do osiągnięcia celu."
    ),
    dbc.Row([
        dbc.Col([
            dbc.Label("Docelowy udział OZE (%)", style={"color": "#ccc"}),
            dcc.Slider(
                id="cr-target-slider",
                min=30,
                max=100,
                value=50,
                marks={i: f"{i}%" for i in range(30, 101, 10)},
                step=5,
            ),
        ], md=6, className="mb-3"),
    ]),
    dbc.Card(
        dbc.CardBody(
            dcc.Graph(id="cr-gap-graph", style={"height": "420px"}),
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
    Output("cr-share-graph", "figure"),
    Output("cr-growth-table", "data"),
    Output("cr-growth-table", "columns"),
    Output("cr-tech-abs-graph", "figure"),
    Output("cr-tech-pct-graph", "figure"),
    Output("cr-growth-abs-graph", "figure"),
    Output("cr-cagr-graph", "figure"),
    Output("cr-gap-graph", "figure"),
    Input("cr-countries", "value"),
    Input("cr-year-range", "value"),
    Input("cr-target-slider", "value"),
)
def update_compare_renewables(countries, year_range, target_pct):
    empty_fig = go.Figure()

    if not countries or not year_range:
        return empty_fig, [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    # --- Section 1: Share trajectories ---
    df_share = get_renewable_share_comparison(countries, start_year, end_year)

    if df_share.empty:
        return empty_fig, [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    df_share = df_share.copy()
    df_share["country_name"] = df_share["country"].map(COUNTRY_NAMES_PL)

    fig_share = px.line(
        df_share,
        x="year",
        y="renewable_share",
        color="country_name",
        markers=True,
        labels={
            "year": "Rok",
            "renewable_share": "Udział OZE",
            "country_name": "Kraj",
        },
        title="Udział OZE w generacji",
    )
    fig_share.update_yaxes(tickformat=".0%", range=[0, 1])

    if len(countries) >= 3:
        avg_by_year = df_share.groupby("year")["renewable_share"].mean().reset_index()
        fig_share.add_trace(go.Scatter(
            x=avg_by_year["year"],
            y=avg_by_year["renewable_share"],
            mode="lines",
            name="Średnia wyboru",
            line=dict(color="#e0e0e0", width=2, dash="dot"),
        ))

    # Growth summary table
    df_growth = get_renewable_growth_comparison(countries, start_year, end_year)

    if df_growth.empty:
        growth_data = []
        growth_cols = []
    else:
        df_growth_sorted = df_growth.sort_values("share_gain_pp", ascending=False).copy()
        df_growth_sorted["kraj"] = df_growth_sorted["country"].map(COUNTRY_NAMES_PL)

        growth_cols = [
            {"name": "Kraj", "id": "kraj"},
            {"name": f"Udział {start_year} (%)", "id": "share_start_pct"},
            {"name": f"Udział {end_year} (%)", "id": "share_end_pct"},
            {"name": "Przyrost (pp)", "id": "share_gain_pp"},
            {"name": "Wzrost (%)", "id": "growth_pct"},
            {"name": "CAGR (%)", "id": "cagr_pct"},
        ]
        growth_data = df_growth_sorted.to_dict("records")

    # --- Section 2: Technology mix (latest year) ---
    df_tech = get_technology_mix_comparison(countries, end_year)

    if df_tech.empty:
        fig_tech_abs = empty_fig
        fig_tech_pct = empty_fig
    else:
        df_tech = df_tech.copy()
        df_tech["country_name"] = df_tech["country"].map(COUNTRY_NAMES_PL)

        fuel_map_pl = {
            "Hydro": "Hydro", "Wind": "Wiatr", "Solar": "Słońce",
            "Geothermal": "Geotermia", "Other renewables": "Inne OZE",
        }
        df_tech["fuel_pl"] = df_tech["fuel"].map(fuel_map_pl).fillna(df_tech["fuel"])

        fig_tech_abs = px.bar(
            df_tech,
            x="country_name",
            y="generation_gwh",
            color="fuel_pl",
            labels={"country_name": "Kraj", "generation_gwh": "Generacja (GWh)", "fuel_pl": "Technologia"},
            title=f"Generacja OZE wg technologii — {end_year}",
            color_discrete_map={
                "Hydro": "#06b6d4",
                "Wiatr": "#6bcf7f",
                "Słońce": "#ffd93d",
                "Geotermia": "#f97316",
                "Inne OZE": "#a78bfa",
            },
        )

        fig_tech_pct = px.bar(
            df_tech,
            x="country_name",
            y="share_of_renewable",
            color="fuel_pl",
            labels={"country_name": "Kraj", "share_of_renewable": "% w OZE", "fuel_pl": "Technologia"},
            title=f"Struktura źródeł w OZE — {end_year}",
            color_discrete_map={
                "Hydro": "#06b6d4",
                "Wiatr": "#6bcf7f",
                "Słońce": "#ffd93d",
                "Geotermia": "#f97316",
                "Inne OZE": "#a78bfa",
            },
        )
        fig_tech_pct.update_layout(barmode="stack")
        fig_tech_pct.update_yaxes(range=[0, 100])

    # --- Section 3: Growth race ---
    if df_growth.empty:
        fig_growth_abs = empty_fig
        fig_cagr = empty_fig
    else:
        df_growth_sorted2 = df_growth.sort_values("absolute_growth_gwh", ascending=False).copy()
        df_growth_sorted2["country_name"] = df_growth_sorted2["country"].map(COUNTRY_NAMES_PL)

        fig_growth_abs = go.Figure()
        fig_growth_abs.add_trace(go.Bar(
            x=df_growth_sorted2["country_name"],
            y=df_growth_sorted2["absolute_growth_gwh"],
            marker_color=df_growth_sorted2["absolute_growth_gwh"].apply(
                lambda v: "#00d4aa" if v > 0 else "#ff6b6b"
            ),
            text=df_growth_sorted2["absolute_growth_gwh"].apply(lambda v: f"{v:+,.0f}"),
            textposition="outside",
            textfont=dict(color="#ccc"),
        ))
        fig_growth_abs.update_layout(
            title=f"Przyrost generacji OZE ({start_year}→{end_year})",
            xaxis_title="Kraj",
            yaxis_title="Wzrost (GWh)",
            showlegend=False,
        )

        df_cagr = df_growth.dropna(subset=["cagr_pct"]).sort_values("cagr_pct", ascending=False).copy()
        df_cagr["country_name"] = df_cagr["country"].map(COUNTRY_NAMES_PL)

        fig_cagr = go.Figure()
        fig_cagr.add_trace(go.Bar(
            x=df_cagr["country_name"],
            y=df_cagr["cagr_pct"],
            marker_color=df_cagr["cagr_pct"].apply(
                lambda v: "#00d4aa" if v > 3 else ("#ffd93d" if v > 0 else "#ff6b6b")
            ),
            text=df_cagr["cagr_pct"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
            textfont=dict(color="#ccc"),
        ))
        fig_cagr.update_layout(
            title=f"Średnioroczne tempo wzrostu ({start_year}→{end_year})",
            xaxis_title="Kraj",
            yaxis_title="CAGR (%)",
            showlegend=False,
        )

    # --- Section 4: Gap to target ---
    df_gap = get_renewable_gap_to_target(countries, end_year, target_pct)

    if df_gap.empty:
        fig_gap = empty_fig
    else:
        df_gap_sorted = df_gap.sort_values("gap_pp", ascending=True).copy()
        df_gap_sorted["country_name"] = df_gap_sorted["country"].map(COUNTRY_NAMES_PL)

        fig_gap = go.Figure()

        fig_gap.add_trace(go.Bar(
            x=df_gap_sorted["country_name"],
            y=df_gap_sorted["current_share_pct"],
            name="Aktualny udział (%)",
            marker_color=df_gap_sorted["status"].apply(
                lambda s: "#00d4aa" if s == "Above target" else ("#ffd93d" if s == "Close" else "#f97316")
            ),
        ))

        fig_gap.add_hline(
            y=target_pct,
            line_dash="dash",
            line_color="#ff6b6b",
            annotation_text=f"Cel: {target_pct}%",
            annotation_position="top right",
            annotation_font_color="#ff6b6b",
        )

        for _, row in df_gap_sorted.iterrows():
            if row["gap_pp"] > 0:
                fig_gap.add_annotation(
                    x=row["country_name"],
                    y=row["current_share_pct"] + 2,
                    text=f"−{row['gap_pp']:.0f}pp<br>({row['additional_gwh_needed']:,.0f} GWh potrzeba)",
                    showarrow=False,
                    font=dict(size=9, color="#ff6b6b"),
                )

        fig_gap.update_layout(
            title=f"Dystans do celu {target_pct}% OZE — {end_year}",
            xaxis_title="Kraj",
            yaxis_title="Udział OZE (%)",
            yaxis=dict(range=[0, max(target_pct + 20, df_gap_sorted["current_share_pct"].max() + 15)]),
            showlegend=False,
        )

    return (
        fig_share, growth_data, growth_cols,
        fig_tech_abs, fig_tech_pct,
        fig_growth_abs, fig_cagr, fig_gap
    )