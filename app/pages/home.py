import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import pandas as pd

from app.backend.data_access import (
    load_eurostat_share_annual,
    load_monthly,
)

dash.register_page(
    __name__,
    path="/",
    name="Strona główna",
    title="Analizator Transformacji Energetycznej Europy",
)

# -----------------------------------------------------------------------
# Auto-computed key findings
# -----------------------------------------------------------------------

def _compute_key_findings():
    """Compute headline statistics for the home page."""
    df = load_eurostat_share_annual()
    df = df.dropna(subset=["renewable_share", "total_generation_gwh"])

    latest_year = int(df["year"].max())
    df_latest = df[df["year"] == latest_year]

    earliest_year = int(df[df["year"] >= 2018]["year"].min())
    df_earliest = df[df["year"] == earliest_year]

    avg_share_latest = df_latest["renewable_share"].mean() * 100
    avg_share_earliest = df_earliest["renewable_share"].mean() * 100

    merged = df_latest[["country", "renewable_share"]].merge(
        df_earliest[["country", "renewable_share"]],
        on="country", suffixes=("_now", "_then")
    )
    merged["change_pp"] = (merged["renewable_share_now"] - merged["renewable_share_then"]) * 100
    merged = merged.sort_values("change_pp", ascending=False)

    fastest = merged.iloc[0]
    slowest = merged.iloc[-1]

    above_50 = (df_latest["renewable_share"] >= 0.5).sum()
    below_25 = (df_latest["renewable_share"] < 0.25).sum()
    total_countries = len(df_latest)

    pl_row = df_latest[df_latest["country"] == "PL"]
    pl_share = pl_row["renewable_share"].iloc[0] * 100 if not pl_row.empty else None
    pl_rank = int((df_latest["renewable_share"] > pl_row["renewable_share"].iloc[0]).sum() + 1) if not pl_row.empty else None

    df_load = load_monthly()
    df_load["year"] = df_load["year_month"].dt.year
    total_load_twh = df_load[df_load["year"] == latest_year]["load_sum"].sum() / 1_000_000

    return {
        "latest_year": latest_year,
        "earliest_year": earliest_year,
        "avg_share_latest": round(avg_share_latest, 1),
        "avg_share_earliest": round(avg_share_earliest, 1),
        "fastest_country": fastest["country"],
        "fastest_change": round(fastest["change_pp"], 1),
        "slowest_country": slowest["country"],
        "slowest_change": round(slowest["change_pp"], 1),
        "above_50": above_50,
        "below_25": below_25,
        "total_countries": total_countries,
        "pl_share": round(pl_share, 1) if pl_share else "N/A",
        "pl_rank": pl_rank,
        "total_load_twh": round(total_load_twh, 1),
    }

_findings = _compute_key_findings()

# -----------------------------------------------------------------------
# Helper components
# -----------------------------------------------------------------------

def _nav_card(title, description, href):
    """Navigation card for a page."""
    return dbc.Card(
        dbc.CardBody([
            html.H6(title, style={"color": "#fff", "marginBottom": "0.3rem"}),
            html.P(description, style={"color": "#888", "fontSize": "0.75rem", "marginBottom": "0.8rem"}),
            dbc.Button("Otwórz", href=href, color="primary", size="sm", outline=True),
        ], style={"textAlign": "center", "padding": "1.2rem 0.8rem"}),
        style={
            "backgroundColor": "#2d2d2d",
            "border": "1px solid #3d3d3d",
            "borderRadius": "10px",
        },
        className="h-100",
    )

def _finding_item(text, highlight=None, highlight_color="#00d4aa"):
    """Single finding bullet point."""
    if highlight:
        return html.Li([
            html.Span(highlight, style={"color": highlight_color, "fontWeight": "bold"}),
            html.Span(f" {text}", style={"color": "#bbb"}),
        ], style={"marginBottom": "0.5rem"})
    else:
        return html.Li(text, style={"color": "#bbb", "marginBottom": "0.5rem"})

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    html.Div([
        html.H1(
            "Analizator Transformacji Energetycznej Europy",
            style={"color": "#fff", "fontWeight": "bold", "marginBottom": "0.3rem", "fontSize": "2rem"},
        ),
        html.P(
            "Interaktywna platforma analityczna do oceny transformacji energetycznej krajów europejskich",
            style={"color": "#999", "fontSize": "1rem", "marginBottom": "0.5rem"},
        ),
        html.P(
            f"37 krajów · 2015–{_findings['latest_year']} · ENTSO-E + Eurostat",
            style={"color": "#666", "fontSize": "0.85rem"},
        ),
    ], style={"textAlign": "center", "padding": "2rem 0 1.5rem 0"}),

    # --- DIAGNOZA ---
    html.Div([
        html.H5([
            html.Span("01 ", style={"color": "#ffffff"}),
            "Przegląd danych ogólnych"
        ], style={"color": "#ccc", "marginBottom": "1rem"}),
        html.P("Ocena stanu obecnego: poziomy popytu, udział OZE, saldo wymiany transgranicznej.",
               style={"color": "#666", "fontSize": "0.85rem", "marginBottom": "1rem"}),
    ]),
    dbc.Row([
        dbc.Col(_nav_card("Przegląd kraju", "KPI kraju, obciążenie, szczyt zapotrzebowania, pozycja handlowa", "/country-overview"), md=4, className="mb-3"),
        dbc.Col(_nav_card("Mapa Europy", "Kartogram: OZE, obciążenie, przepływy, samowystarczalność", "/map"), md=4, className="mb-3"),
        dbc.Col(_nav_card("Porównanie krajów", "Wielokrajowe obciążenie, indeksowane trendy, zmiany r/r", "/compare-countries"), md=4, className="mb-3"),
    ]),

    # --- ZROZUMIENIE ---
    html.Div([
        html.H5([
            html.Span("02 ", style={"color": "#ffffff"}),
            "Zrozumienie wzorców popytu i wytwarzania"
        ], style={"color": "#ccc", "marginTop": "2rem", "marginBottom": "1rem"}),
        html.P("Dekompozycja wzorców popytu — kiedy i jak zużywana jest energia elektryczna.",
               style={"color": "#666", "fontSize": "0.85rem", "marginBottom": "1rem"}),
    ]),
    dbc.Row([
        dbc.Col(_nav_card("Wzorce obciążeń", "Cykle dzienne, dzień roboczy/weekend, mapa sezonowa", "/load-patterns"), md=4, className="mb-3"),
        dbc.Col(_nav_card("Sezonowość", "Dekompozycja STL: trend, sezon, anomalie", "/seasonality"), md=4, className="mb-3"),
        dbc.Col(_nav_card("Połączenia transgraniczne", "Import/eksport transgraniczny, bilans handlowy", "/interconnectors"), md=4, className="mb-3"),
    ]),

    # --- POMIAR ---
    html.Div([
        html.H5([
            html.Span("03 ", style={"color": "#ffffff"}),
            "Pomiar postępów transformacji"
        ], style={"color": "#ccc", "marginTop": "2rem", "marginBottom": "1rem"}),
        html.P("Pomiar wzrostu OZE, wypierania paliw kopalnych i postępów względem celów.",
               style={"color": "#666", "fontSize": "0.85rem", "marginBottom": "1rem"}),
    ]),
    dbc.Row([
        dbc.Col(_nav_card("Moc i wytwarzanie OZE", "Wielkość i udział wytwarzania wg technologii", "/renewables-capacity"), md=3, className="mb-3"),
        dbc.Col(_nav_card("OZE vs obciążenie", "Pokrycie zapotrzebowania, spadek zależności od paliw kopalnych", "/renewables-vs-load"), md=3, className="mb-3"),
        dbc.Col(_nav_card("Tempo transformacji", "Wzrost r/r, CAGR, wykrywanie przyspieszenia", "/energy-transition-pace"), md=3, className="mb-3"),
        dbc.Col(_nav_card("Porównanie OZE", "Rankingi, struktura technologiczna, dystans do celu", "/compare-renewables"), md=3, className="mb-3"),
    ]),

    # --- ANALIZA ---
    html.Div([
        html.H5([
            html.Span("04 ", style={"color": "#ffffff"}),
            "Analiza zależności oraz grupowanie"
        ], style={"color": "#ccc", "marginTop": "2rem", "marginBottom": "1rem"}),
        html.P("Zastosowanie metod statystycznych do wykrywania grup strukturalnych i zależności.",
               style={"color": "#666", "fontSize": "0.85rem", "marginBottom": "1rem"}),
    ]),
    dbc.Row([
        dbc.Col(_nav_card("Samowystarczalność", "Niezależność energetyczna i trendy zależności importowej", "/self-sufficiency"), md=4, className="mb-3"),
        dbc.Col(_nav_card("Grupowanie", "K-Means, mapa korelacji, przebiegi", "/clustering"), md=4, className="mb-3"),
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.Div(style={"fontSize": "1.8rem", "marginBottom": "0.5rem"}),
                    html.H6("Metodologia", style={"color": "#fff", "marginBottom": "0.3rem"}),
                    html.P("Źródła danych, metody i proces przetwarzania",
                           style={"color": "#888", "fontSize": "0.75rem", "marginBottom": "0.8rem"}),
                    dbc.Button("Otwórz", href="/methodology", color="secondary", size="sm", outline=True),
                ], style={"textAlign": "center", "padding": "1.2rem 0.8rem"}),
                style={
                    "backgroundColor": "#2a2a2a",
                    "border": "1px dashed #555",
                    "borderRadius": "10px",
                },
                className="h-100",
            ),
            md=4, className="mb-3",
        ),
    ]),
    
    # Key Findings panel
    dbc.Card(
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H5("Kluczowe wyniki", style={"color": "#fff", "marginBottom": "1rem"}),
                    html.Ul([
                        _finding_item(
                            f"średni udział OZE w Europie ({_findings['latest_year']}), wzrost z {_findings['avg_share_earliest']}% w {_findings['earliest_year']}",
                            highlight=f"{_findings['avg_share_latest']}%",
                        ),
                        _finding_item(
                            f"— najszybszy wzrost OZE (+{_findings['fastest_change']} pp od {_findings['earliest_year']})",
                            highlight=_findings["fastest_country"],
                        ),
                        _finding_item(
                            f"krajów przekracza 50% udziału OZE; {_findings['below_25']} pozostaje poniżej 25%",
                            highlight=str(_findings["above_50"]),
                        ),
                        _finding_item(
                            f"Polska: {_findings['pl_share']}% udziału OZE (pozycja {_findings['pl_rank']}/{_findings['total_countries']})",
                            highlight="PL",
                            highlight_color="#ffd93d",
                        ),
                        _finding_item(
                            f"TWh całkowitego zużycia energii elektrycznej w Europie ({_findings['latest_year']})",
                            highlight=f"{_findings['total_load_twh']:,.0f}",
                            highlight_color="#3391ff",
                        ),
                    ], style={"listStyleType": "none", "paddingLeft": "0"}),
                ], md=7),
                dbc.Col([
                    html.Div([
                        html.Div("Średni udział OZE w UE", style={"color": "#888", "fontSize": "0.8rem"}),
                        html.Div(f"{_findings['avg_share_latest']}%", style={
                            "fontSize": "3rem", "fontWeight": "bold", "color": "#00d4aa"
                        }),
                        html.Div(f"+{_findings['avg_share_latest'] - _findings['avg_share_earliest']:.1f} pp od {_findings['earliest_year']}", style={
                            "color": "#6bcf7f", "fontSize": "0.9rem"
                        }),
                    ], style={"textAlign": "center", "padding": "2rem 0"}),
                ], md=5),
            ]),
        ]),
        className="mb-4",
        style={
            "backgroundColor": "#2a2a2a",
            "border": "1px dashed #555",
            "borderRadius": "10px",
        },
    ),

    # Footer
    html.Div([
        html.Hr(style={"borderColor": "#333", "marginTop": "2rem"}),
        html.P([
            "Źródła danych: ",
            html.A("ENTSO-E Transparency Platform", href="https://transparency.entsoe.eu/", target="_blank", style={"color": "#3391ff"}),
            " + ",
            html.A("Eurostat", href="https://ec.europa.eu/eurostat", target="_blank", style={"color": "#3391ff"}),
            f" · {_findings['total_countries']} krajów · 2015–{_findings['latest_year']}",
        ], style={"color": "#555", "fontSize": "0.8rem", "textAlign": "center"}),
    ]),
])
