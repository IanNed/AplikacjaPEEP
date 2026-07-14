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
    get_self_sufficiency,
    get_self_sufficiency_comparison,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/self-sufficiency",
    name="Samowystarczalność",
    title="Samowystarczalność i zależność importowa",
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
        "Samowystarczalność i zależność importowa",
        "Łączy generację krajową (Eurostat), obciążenie (ENTSO-E) i przepływy "
        "transgraniczne (ENTSO-E), aby ocenić, na ile kraj jest w stanie pokryć własne "
        "zapotrzebowanie — i czy wzrost OZE zmniejsza zależność od importu."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Kraje", style={"color": "#ccc"}),
                dcc.Dropdown(
                    id="ss-countries",
                    options=COUNTRY_OPTIONS,
                    value=["DE", "PL", "FR", "IT", "ES"],
                    multi=True,
                    clearable=False,
                ),
            ], md=7),
            dbc.Col([
                dbc.Label("Zakres lat", style={"color": "#ccc"}),
                dcc.RangeSlider(
                    id="ss-year-range",
                    min=MIN_YEAR,
                    max=MAX_YEAR,
                    value=[MIN_YEAR, MAX_YEAR],
                    marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                    allowCross=False,
                ),
            ], md=5),
        ]),
    ),

    # Section 1: Comparison table
    section_header(
        "Porównanie (ostatni rok)",
        "Samowystarczalność > 1 = producent netto. Zależność importowa = udział importu netto w obciążeniu."
    ),
    dash_table.DataTable(
        id="ss-comparison-table",
        columns=[],
        data=[],
        page_size=15,
        sort_action="native",
        style_table=DARK_TABLE_STYLE["style_table"],
        style_cell=DARK_TABLE_STYLE["style_cell"],
        style_header=DARK_TABLE_STYLE["style_header"],
        style_data_conditional=[
            *DARK_TABLE_STYLE["style_data_conditional"],
            {"if": {"filter_query": "{self_sufficiency_ratio} >= 1"}, "backgroundColor": "#1a3a2a", "color": "#6bcf7f"},
            {"if": {"filter_query": "{self_sufficiency_ratio} < 1"}, "backgroundColor": "#3a2a1a", "color": "#ffd93d"},
            {"if": {"filter_query": "{import_dependency} > 0.2"}, "color": "#ff6b6b"},
        ],
    ),

    # Section 2: Time series
    section_header("Samowystarczalność w czasie"),
    dbc.Row([
        dbc.Col(chart_card("Wskaźnik samowystarczalności (generacja / obciążenie)", "ss-ratio-graph"), md=6),
        dbc.Col(chart_card("Zależność importowa (import netto / obciążenie)", "ss-import-dep-graph"), md=6),
    ]),

    # Section 3: Renewable coverage
    section_header(
        "Samowystarczalność OZE",
        "Jaka część zapotrzebowania może być pokryta przez krajowe OZE? Wzrost = wypieranie fossil + importu."
    ),
    dbc.Row([
        dbc.Col(chart_card("Pokrycie zapotrzebowania przez OZE", "ss-renewable-coverage-graph"), md=6),
        dbc.Col(chart_card("Bilans energetyczny", "ss-balance-graph"), md=6),
    ]),

    # Section 4: Detail table
    section_header("Szczegółowe dane roczne"),
    dbc.Row([
        dbc.Col([
            dbc.Label("Wybierz kraj do szczegółów", style={"color": "#ccc"}),
            dcc.Dropdown(
                id="ss-detail-country",
                options=COUNTRY_OPTIONS,
                value="PL",
                clearable=False,
                style={"width": "200px"},
            ),
        ], md=3, className="mb-3"),
    ]),
    dash_table.DataTable(
        id="ss-detail-table",
        columns=[],
        data=[],
        page_size=12,
        sort_action="native",
        **DARK_TABLE_STYLE,
    ),
])

# -----------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------

@callback(
    Output("ss-comparison-table", "data"),
    Output("ss-comparison-table", "columns"),
    Output("ss-ratio-graph", "figure"),
    Output("ss-import-dep-graph", "figure"),
    Output("ss-renewable-coverage-graph", "figure"),
    Output("ss-balance-graph", "figure"),
    Input("ss-countries", "value"),
    Input("ss-year-range", "value"),
)
def update_self_sufficiency(countries, year_range):
    empty_fig = go.Figure()

    if not countries or not year_range:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    if isinstance(countries, str):
        countries = [countries]

    start_year, end_year = year_range

    # --- Comparison table (latest year) ---
    df_comp = get_self_sufficiency_comparison(countries, start_year, end_year)

    if df_comp.empty:
        return [], [], empty_fig, empty_fig, empty_fig, empty_fig

    df_comp = df_comp.copy()
    df_comp["kraj"] = df_comp["country"].map(COUNTRY_NAMES_PL)

    comp_columns = [
        {"name": "Kraj", "id": "kraj"},
        {"name": "Rok", "id": "year"},
        {"name": "Samowystarczalność", "id": "self_sufficiency_ratio"},
        {"name": "Zależność import.", "id": "import_dependency"},
        {"name": "Samowystarczalność OZE", "id": "renewable_self_sufficiency"},
        {"name": "Nadwyżka eksportowa", "id": "export_surplus"},
    ]
    comp_data = df_comp.to_dict("records")

    # --- Time series charts (all selected countries) ---
    all_frames = []
    for country in countries:
        df = get_self_sufficiency(country)
        if df.empty:
            continue
        df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()
        df["country_name"] = COUNTRY_NAMES_PL.get(country, country)
        all_frames.append(df)

    if not all_frames:
        return comp_data, comp_columns, empty_fig, empty_fig, empty_fig, empty_fig

    df_all = pd.concat(all_frames, ignore_index=True)

    # Self-sufficiency ratio over time
    fig_ratio = px.line(
        df_all,
        x="year",
        y="self_sufficiency_ratio",
        color="country_name",
        markers=True,
        labels={
            "year": "Rok",
            "self_sufficiency_ratio": "Generacja / Obciążenie",
            "country_name": "Kraj",
        },
        title="Wskaźnik samowystarczalności w czasie",
    )
    fig_ratio.add_hline(
        y=1.0, line_dash="dash", line_color="rgba(255,255,255,0.4)",
        annotation_text="Samowystarczalny (wskaźnik=1)",
        annotation_position="top left",
        annotation_font_color="#ccc",
    )

    # Import dependency over time
    fig_import = px.line(
        df_all,
        x="year",
        y="import_dependency",
        color="country_name",
        markers=True,
        labels={
            "year": "Rok",
            "import_dependency": "Import netto / Obciążenie",
            "country_name": "Kraj",
        },
        title="Zależność importowa w czasie",
    )
    fig_import.update_yaxes(tickformat=".0%")
    fig_import.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")

    # Renewable self-sufficiency over time
    fig_renew = px.line(
        df_all,
        x="year",
        y="renewable_self_sufficiency",
        color="country_name",
        markers=True,
        labels={
            "year": "Rok",
            "renewable_self_sufficiency": "Generacja OZE / Obciążenie",
            "country_name": "Kraj",
        },
        title="Samowystarczalność OZE (OZE / zapotrzebowanie całkowite)",
    )
    fig_renew.update_yaxes(tickformat=".0%", range=[0, None])

    # Energy balance stacked bar (first selected country)
    first_country = countries[0]
    first_country_name = COUNTRY_NAMES_PL.get(first_country, first_country)
    df_first = df_all[df_all["country_name"] == first_country_name].copy()

    if not df_first.empty:
        fig_balance = go.Figure()

        fig_balance.add_trace(go.Bar(
            x=df_first["year"],
            y=df_first["renewable_generation_gwh"],
            name="Generacja OZE",
            marker_color="#00d4aa",
        ))

        df_first["non_renewable_gwh"] = (
            df_first["total_generation_gwh"] - df_first["renewable_generation_gwh"]
        )
        fig_balance.add_trace(go.Bar(
            x=df_first["year"],
            y=df_first["non_renewable_gwh"],
            name="Generacja nie-OZE",
            marker_color="#555",
        ))

        df_first["net_import_positive"] = df_first["net_import_gwh"].clip(lower=0)
        fig_balance.add_trace(go.Bar(
            x=df_first["year"],
            y=df_first["net_import_positive"],
            name="Import netto",
            marker_color="#f97316",
        ))

        fig_balance.add_trace(go.Scatter(
            x=df_first["year"],
            y=df_first["annual_load_gwh"],
            mode="lines+markers",
            name="Obciążenie całkowite",
            line=dict(color="#3391ff", width=3),
        ))

        fig_balance.update_layout(
            barmode="stack",
            title=f"Bilans energetyczny — {first_country_name}",
            xaxis_title="Rok",
            yaxis_title="GWh",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
    else:
        fig_balance = empty_fig

    return comp_data, comp_columns, fig_ratio, fig_import, fig_renew, fig_balance

@callback(
    Output("ss-detail-table", "data"),
    Output("ss-detail-table", "columns"),
    Input("ss-detail-country", "value"),
    Input("ss-year-range", "value"),
)
def update_detail_table(country, year_range):
    if not country or not year_range:
        return [], []

    start_year, end_year = year_range

    df = get_self_sufficiency(country)
    if df.empty:
        return [], []

    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()

    if df.empty:
        return [], []

    df_view = pd.DataFrame({
        "year": df["year"].astype(int),
        "generation_gwh": df["total_generation_gwh"].round(1),
        "renewable_gwh": df["renewable_generation_gwh"].round(1),
        "load_gwh": df["annual_load_gwh"].round(1),
        "imports_gwh": df["annual_import_gwh"].round(1),
        "exports_gwh": df["annual_export_gwh"].round(1),
        "net_import_gwh": df["net_import_gwh"].round(1),
        "self_sufficiency": df["self_sufficiency_ratio"].round(3),
        "import_dep_pct": (df["import_dependency"] * 100).round(1),
        "renew_self_suff_pct": (df["renewable_self_sufficiency"] * 100).round(1),
    })

    columns = [
        {"name": "Rok", "id": "year"},
        {"name": "Generacja (GWh)", "id": "generation_gwh"},
        {"name": "OZE (GWh)", "id": "renewable_gwh"},
        {"name": "Obciążenie (GWh)", "id": "load_gwh"},
        {"name": "Import (GWh)", "id": "imports_gwh"},
        {"name": "Eksport (GWh)", "id": "exports_gwh"},
        {"name": "Import netto (GWh)", "id": "net_import_gwh"},
        {"name": "Samowystarczalność", "id": "self_sufficiency"},
        {"name": "Zal. import. (%)", "id": "import_dep_pct"},
        {"name": "Samow. OZE (%)", "id": "renew_self_suff_pct"},
    ]

    return df_view.to_dict("records"), columns
