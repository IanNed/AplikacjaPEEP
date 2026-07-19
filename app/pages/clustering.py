import dash
from dash import html, dcc, callback, Input, Output
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import dash_bootstrap_components as dbc

from app.backend.data_access import (
    get_clustering_results,
    get_load_correlation_matrix,
    get_transition_trajectory_clusters,
    get_map_year_bounds,
    COUNTRY_NAMES_PL,
)

from app.components import (
    page_header, control_panel, chart_card,
    section_header, DARK_TABLE_STYLE,
)

dash.register_page(
    __name__,
    path="/clustering",
    name="Grupowanie",
    title="Grupowanie i korelacja",
)

# -----------------------------------------------------------------------
# Data setup
# -----------------------------------------------------------------------

MIN_YEAR, MAX_YEAR = get_map_year_bounds()

CLUSTER_FEATURE_LABELS = {
    "share_ra100": "Hydro",
    "share_ra300": "Wiatr",
    "share_ra400": "Słońce",
    "share_ra000": "OZE (łącznie)",
    "share_c0000": "Węgiel",
    "share_g3000": "Gaz",
    "share_n9000": "Atom",
}

CLUSTER_COLORS = px.colors.qualitative.Set2

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------

layout = html.Div([

    page_header(
        "Grupowanie i analiza korelacji",
        "Podział krajów europejskich na grupy na podstawie źródeł wytwarzania i wzorców zapotrzebowania."
    ),

    # Controls
    control_panel(
        dbc.Row([
            dbc.Col([
                dbc.Label("Rok (dla grupowania wg źródeł wytwarzania)", style={"color": "#ccc"}),
                dcc.Slider(
                    id="cl-year",
                    min=MIN_YEAR,
                    max=MAX_YEAR,
                    value=MAX_YEAR,
                    marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1)},
                    step=1,
                ),
            ], md=7),
            dbc.Col([
                dbc.Label("Liczba grup", style={"color": "#ccc"}),
                dcc.Slider(
                    id="cl-n-clusters",
                    min=2,
                    max=7,
                    value=4,
                    marks={i: str(i) for i in range(2, 8)},
                    step=1,
                ),
            ], md=5),
        ]),
    ),

    # Section 1: Clustering by generation source
    section_header(
        "Grupowanie wg źródeł wytwarzania",
        "Kraje pogrupowane według udziałów poszczególnych źródeł energii (hydro, wiatr, słońce, węgiel, gaz, atom). "
        "Analiza głównych składowych redukuje wymiary do wizualizacji 2D."
    ),
    dbc.Row([
        dbc.Col(chart_card("Analiza głównych składowych — grupy krajów", "cl-pca-graph"), md=7),
        dbc.Col(chart_card("Średnia struktura wytwarzania na grupę", "cl-profile-graph"), md=5),
    ]),

    # Membership table
    section_header("Przynależność do grup"),
    dash_table.DataTable(
        id="cl-membership-table",
        columns=[],
        data=[],
        page_size=12,
        sort_action="native",
        filter_action="native",
        **DARK_TABLE_STYLE,
    ),

    # Section 2: Load correlation
    section_header(
        "Korelacja wzorców obciążeń",
        "Współczynnik korelacji Pearsona miesięcznych przebiegów zapotrzebowania. Obliczony jednokrotnie dla całego okresu."
    ),
    dcc.Graph(
        id="cl-heatmap-graph",
        style={"height": "600px"},
    ),

    # Section 3: Trajectory clustering
    section_header(
        "Grupowanie wg przebiegu transformacji",
        "Podział krajów według kształtu zmian udziału OZE w kolejnych latach."
    ),
    chart_card("Przebieg udziału OZE wg grup", "cl-trajectory-graph", height="450px"),
    dash_table.DataTable(
        id="cl-trajectory-table",
        columns=[],
        data=[],
        page_size=15,
        sort_action="native",
        **DARK_TABLE_STYLE,
    ),
])

# -----------------------------------------------------------------------
# Callback 1: Clustering by generation source
# -----------------------------------------------------------------------

@callback(
    Output("cl-pca-graph", "figure"),
    Output("cl-profile-graph", "figure"),
    Output("cl-membership-table", "data"),
    Output("cl-membership-table", "columns"),
    Input("cl-year", "value"),
    Input("cl-n-clusters", "value"),
)
def update_mix_clustering(year, n_clusters):
    empty_fig = go.Figure()

    if not year or not n_clusters:
        return empty_fig, empty_fig, [], []

    year = int(year)
    n_clusters = int(n_clusters)

    df_clustered, df_centers = get_clustering_results(year, n_clusters)

    if df_clustered.empty:
        return empty_fig, empty_fig, [], []

    pca_var_x = df_clustered["pca_var_x"].iloc[0]
    pca_var_y = df_clustered["pca_var_y"].iloc[0]
    df_clustered["cluster_label"] = "Grupa " + df_clustered["cluster"].astype(str)

    fig_pca = px.scatter(
        df_clustered,
        x="pca_x",
        y="pca_y",
        color="cluster_label",
        hover_name="country_name",
        hover_data={"pca_x": False, "pca_y": False, "cluster_label": False, "country": True},
        text="country",
        color_discrete_sequence=CLUSTER_COLORS,
        title=f"Kraje pogrupowane wg źródeł wytwarzania — {year}",
        labels={
            "pca_x": f"Składowa 1 ({pca_var_x}% wariancji)",
            "pca_y": f"Składowa 2 ({pca_var_y}% wariancji)",
        },
    )
    fig_pca.update_traces(textposition="top center", textfont_size=9)

    feature_cols = [c for c in df_centers.columns if c.startswith("share_")]
    df_profile_long = df_centers.melt(
        id_vars=["cluster"], value_vars=feature_cols,
        var_name="feature", value_name="avg_share",
    )
    df_profile_long["feature_label"] = df_profile_long["feature"].map(CLUSTER_FEATURE_LABELS)
    df_profile_long["cluster_label"] = "Grupa " + df_profile_long["cluster"].astype(str)

    fig_profile = px.bar(
        df_profile_long, x="feature_label", y="avg_share",
        color="cluster_label", barmode="group",
        color_discrete_sequence=CLUSTER_COLORS,
        labels={"feature_label": "Źródło", "avg_share": "Śr. udział", "cluster_label": "Grupa"},
        title="Średnia struktura wytwarzania na grupę",
    )
    fig_profile.update_yaxes(tickformat=".0%")

    table_df = df_clustered[["country", "country_name", "cluster"]].copy()
    table_df["cluster"] = "Grupa " + table_df["cluster"].astype(str)

    for col, label in CLUSTER_FEATURE_LABELS.items():
        if col in df_clustered.columns:
            table_df[label] = (df_clustered[col] * 100).round(1)

    membership_cols = [
        {"name": "Kod", "id": "country"},
        {"name": "Kraj", "id": "country_name"},
        {"name": "Grupa", "id": "cluster"},
    ]
    for label in CLUSTER_FEATURE_LABELS.values():
        if label in table_df.columns:
            membership_cols.append({"name": f"{label} (%)", "id": label})

    return fig_pca, fig_profile, table_df.to_dict("records"), membership_cols

# -----------------------------------------------------------------------
# Callback 2: Heatmap (lazy-loaded, computes on first page visit)
# -----------------------------------------------------------------------

@callback(
    Output("cl-heatmap-graph", "figure"),
    Input("cl-year", "value"),
)
def update_heatmap(_):
    corr_matrix, countries_used = get_load_correlation_matrix(MIN_YEAR, MAX_YEAR)

    if corr_matrix.empty:
        return go.Figure()

    country_labels = [COUNTRY_NAMES_PL.get(c, c) for c in countries_used]

    fig = px.imshow(
        corr_matrix.values,
        x=country_labels,
        y=country_labels,
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        aspect="equal",
        title="Korelacja miesięcznych przebiegów obciążeń (Pearson)",
        labels={"color": "Korelacja"},
    )
    fig.update_layout(xaxis_title="Kraj", yaxis_title="Kraj")
    return fig

# -----------------------------------------------------------------------
# Callback 3: Trajectory clustering
# -----------------------------------------------------------------------

@callback(
    Output("cl-trajectory-graph", "figure"),
    Output("cl-trajectory-table", "data"),
    Output("cl-trajectory-table", "columns"),
    Input("cl-n-clusters", "value"),
)
def update_trajectory_clustering(n_clusters):
    empty_fig = go.Figure()

    if not n_clusters:
        return empty_fig, [], []

    n_clusters = int(n_clusters)

    df_trajectories, df_traj_summary = get_transition_trajectory_clusters(n_clusters)

    if df_trajectories.empty:
        return empty_fig, [], []

    df_trajectories["cluster_label"] = "Grupa " + df_trajectories["cluster"].astype(str)

    fig_trajectory = px.line(
        df_trajectories,
        x="year", y="renewable_share",
        color="cluster_label", line_group="country",
        hover_name="country",
        color_discrete_sequence=CLUSTER_COLORS,
        labels={"year": "Rok", "renewable_share": "Udział OZE", "cluster_label": "Grupa"},
        title="Przebieg udziału OZE wg grup",
    )
    fig_trajectory.update_yaxes(tickformat=".0%", range=[0, 1])
    fig_trajectory.update_traces(opacity=0.6)

    traj_view = df_traj_summary.copy()
    traj_view["cluster"] = "Grupa " + traj_view["cluster"].astype(str)
    traj_view["start_share_pct"] = (traj_view["start_share"] * 100).round(1)
    traj_view["end_share_pct"] = (traj_view["end_share"] * 100).round(1)

    traj_view = traj_view[[
        "country", "country_name", "cluster", "start_share_pct", "end_share_pct", "share_change_pp"
    ]].sort_values(["cluster", "share_change_pp"], ascending=[True, False])

    traj_cols = [
        {"name": "Kod", "id": "country"},
        {"name": "Kraj", "id": "country_name"},
        {"name": "Grupa", "id": "cluster"},
        {"name": "Start (%)", "id": "start_share_pct"},
        {"name": "Koniec (%)", "id": "end_share_pct"},
        {"name": "Zmiana (pp)", "id": "share_change_pp"},
    ]

    return fig_trajectory, traj_view.to_dict("records"), traj_cols