import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine, text
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from scipy.signal import savgol_filter
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Poland Energy & Weather Analysis",
    layout="wide",
    initial_sidebar_state="expanded"
)
###
# Database configuration
###
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "energy_database.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# Data Loading Functions
@st.cache_resource
def get_db_connection():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.error(f"Database Connection Error: {str(e)}")
        return None

# Load energy data from database
@st.cache_data
def load_energy_from_db(_engine):
    try:
        if _engine is None:
            return None
        query = """
        SELECT aed.year, c.CountryName as Country, ep.ProductName as Product,
               a.ActivityName as Activity, aed.Value, u.UnitCode as Unit
        FROM AnnualEnergyData aed
        LEFT JOIN Countries c ON aed.CountryID = c.CountryID
        LEFT JOIN EnergyProducts ep ON aed.ProductID = ep.ProductID
        LEFT JOIN Activities a ON aed.ActivityID = a.ActivityID
        LEFT JOIN Units u ON aed.UnitID = u.UnitID
        WHERE aed.Value IS NOT NULL
        ORDER BY aed.year, c.CountryName
        """
        return pd.read_sql(query, _engine)
    except Exception as e:
        st.error(f"Energy Data Loading Error: {str(e)}")
        return None

# Load weather data from database
@st.cache_data
def load_weather_from_db(_engine):
    try:
        if _engine is None:
            return None
        query = """
        SELECT year, Month, Temperature, Humidity_Percent, WindSpeed, Cloudiness
        FROM WeatherData
        WHERE Temperature IS NOT NULL
        ORDER BY year, Month
        """
        return pd.read_sql(query, _engine)
    except Exception as e:
        st.error(f"Weather Data Loading Error: {str(e)}")
        return None
###
# Data Preparation Functions
###
# Prepare country-specific energy data
@st.cache_data
def prepare_country_energy_data(_energy_df, product_name, activity_name):
    try:
        if product_name == 'Renewables':
            primary_data = _energy_df[
                (_energy_df['Product'] == 'Primary energy') &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            non_renew_data = _energy_df[
                (_energy_df['Product'] == 'Non-renewable energy') &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            
            primary_pivot = primary_data.pivot_table(
                index='year', columns='Country', values='Value', aggfunc='mean'
            )
            non_renew_pivot = non_renew_data.pivot_table(
                index='year', columns='Country', values='Value', aggfunc='mean'
            )
            
            renewables_calc = primary_pivot - non_renew_pivot
            pivot_df = renewables_calc.copy()
            
            renewables_from_db = _energy_df[
                (_energy_df['Product'] == 'Renewables') &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            renewables_db_pivot = renewables_from_db.pivot_table(
                index='year', columns='Country', values='Value', aggfunc='mean'
            )
            
            special_countries = ['Poland', 'Lithuania', 'Czechia']
            for country in special_countries:
                if not renewables_db_pivot.empty and country in renewables_db_pivot.columns:
                    pivot_df[country] = renewables_db_pivot[country]
            
            pivot_df = pivot_df.reset_index()
        else:
            df = _energy_df[
                (_energy_df['Product'] == product_name) &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            pivot_df = df.pivot_table(
                index='year',
                columns='Country',
                values='Value',
                aggfunc='mean'
            ).reset_index()
        return pivot_df
    except Exception as e:
        st.error(f"Error preparing country data: {str(e)}")
        return None

# Data Transformation Functions
def transform_data(_data_df, transformation_mode, selected_countries):
    df = _data_df.copy()
    if transformation_mode != "Levels":
        for c in selected_countries:
            if c in df.columns:
                if transformation_mode == "year-to-year change":
                    df[c] = df[c].diff()
                elif transformation_mode == "Log change":
                    df[c] = np.log(df[c] + 1e-10).diff()
        df = df.dropna()
    return df

# Correlation Analysis Function
def calculate_country_correlations(_data_df, selected_countries):
    try:
        corr_data = _data_df[[col for col in selected_countries if col in _data_df.columns]]
        return corr_data.corr()
    except Exception as e:
        st.error(f"Error calculating correlations: {str(e)}")
        return None

# Correlation Heatmap Function
def create_correlation_heatmap(corr_matrix, title):
    mat = corr_matrix.copy()
    np.fill_diagonal(mat.values, 0)
    mask = np.tril(np.ones(mat.shape, dtype=bool))
    z = mat.values.astype(float).copy()
    z[mask] = np.nan
    text = np.round(mat.values, 2).astype(object)
    text[mask] = ""
    
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=mat.columns,
            y=mat.index,
            colorscale="RdBu",
            zmid=0,
            colorbar=dict(title="Correlation"),
            text=text,
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate='%{y} - %{x}Correlation: %{z:.3f}'
        )
    )
    fig.update_layout(
        title=title,
        height=600,
        xaxis=dict(title="Country", tickangle=-45),
        yaxis=dict(title="Country"),
        template='plotly_white'
    )
    return fig

# Rolling Correlation Function
def create_rolling_correlation(_data_df, country1, country2, window):
    df_pair = _data_df[['year', country1, country2]].dropna()
    if len(df_pair) < window:
        return None
    df_pair = df_pair.set_index('year')
    roll_corr = df_pair[country1].rolling(window).corr(df_pair[country2])
    return roll_corr

# Lagged Correlation Function
@st.cache_data
def create_lagged_correlation_matrix(_energy_df, country1, country2, product, max_lag=5):
    exp_data = _energy_df[
        (_energy_df['Country'] == country1) &
        (_energy_df['Product'] == product) &
        (_energy_df['Activity'] == 'Exports')
    ][['year', 'Value']].rename(columns={'Value': 'Export'}).sort_values('year').reset_index(drop=True)
    
    imp_data = _energy_df[
        (_energy_df['Country'] == country2) &
        (_energy_df['Product'] == product) &
        (_energy_df['Activity'] == 'Imports')
    ][['year', 'Value']].rename(columns={'Value': 'Import'}).sort_values('year').reset_index(drop=True)
    
    correlations = {}
    for lag in range(max_lag + 1):
        imp_lagged = imp_data.copy()
        imp_lagged['year'] = imp_lagged['year'] - lag
        merged = pd.merge(exp_data, imp_lagged, on='year', how='inner')
        if len(merged) >= 10:
            corr = merged['Export'].corr(merged['Import'])
            correlations[lag] = corr
    return correlations

# Import-Export Correlation Function
@st.cache_data
def create_import_export_correlation(_energy_df, country1, country2, product, lag=0):
    exp_data = _energy_df[
        (_energy_df['Country'] == country1) &
        (_energy_df['Product'] == product) &
        (_energy_df['Activity'] == 'Exports')
    ][['year', 'Value']].rename(columns={'Value': f'Export_{country1}'})
    
    imp_data = _energy_df[
        (_energy_df['Country'] == country2) &
        (_energy_df['Product'] == product) &
        (_energy_df['Activity'] == 'Imports')
    ][['year', 'Value']].rename(columns={'Value': f'Import_{country2}'})
    
    if lag > 0:
        imp_data['year'] = imp_data['year'] - lag
    
    merged = pd.merge(exp_data, imp_data, on='year', how='inner')
    if len(merged) < 10:
        return None
    
    corr = merged[f'Export_{country1}'].corr(merged[f'Import_{country2}'])
    return corr, merged

# ARIMA Forecasting Order Selection Function
def select_arima_order(data, max_p=3, max_q=3, d=1):
    best_aic = np.inf
    best_order = None
    best_model = None
    
    for p in range(0, max_p + 1):
        for q in range(0, max_q + 1):
            if p == 0 and q == 0:
                continue
            try:
                model = ARIMA(data, order=(p, d, q))
                fitted = model.fit()
                if fitted.aic < best_aic:
                    best_aic = fitted.aic
                    best_order = (p, d, q)
                    best_model = fitted
            except Exception:
                continue
    
    return best_order, best_model

# ARIMA Forecasting Function
def forecast_arima(_filtered_df, forecast_years=3):
    try:
        data = _filtered_df['Value'].dropna().values
        if len(data) < 15:
            return None, None
        
        order, fitted = select_arima_order(data, max_p=3, max_q=3, d=1)
        if fitted is None:
            return None, None
        
        forecast_result = fitted.get_forecast(steps=forecast_years)
        forecast_ci = forecast_result.conf_int(alpha=0.05)
        
        last_year = int(_filtered_df['year'].max())
        forecast_years_list = list(range(last_year + 1, last_year + forecast_years + 1))
        
        forecast_df = pd.DataFrame({
            'year': forecast_years_list,
            'Forecast': list(forecast_result.predicted_mean),
            'Lower_CI': list(forecast_ci[:, 0]),
            'Upper_CI': list(forecast_ci[:, 1])
        })
        return forecast_df, fitted
    except Exception as e:
        st.error(f"ARIMA Error: {str(e)}")
        return None, None

# ARIMA Plotting Function
def plot_forecast(_filtered_df, _forecast_df, _unit):
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=_filtered_df['year'],
        y=_filtered_df['Value'],
        mode='lines+markers',
        name='Historical Data',
        line=dict(color='blue', width=2),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=_forecast_df['year'],
        y=_forecast_df['Forecast'],
        mode='lines+markers',
        name='Forecast',
        line=dict(color='red', width=2, dash='dash'),
        marker=dict(size=8, symbol='diamond')
    ))
    
    fig.add_trace(go.Scatter(
        x=_forecast_df['year'].tolist() + _forecast_df['year'].tolist()[::-1],
        y=_forecast_df['Upper_CI'].tolist() + _forecast_df['Lower_CI'].tolist()[::-1],
        fill='toself',
        fillcolor='rgba(255, 0, 0, 0.2)',
        line=dict(color='rgba(255, 0, 0, 0)'),
        name='95% Confidence Interval',
        showlegend=True,
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        title="ARIMA Forecast",
        xaxis_title="year",
        yaxis_title=f"Energy Value ({_unit})",
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    return fig

# Trend Decomposition Function
def decompose_trend(_filtered_df):
    try:
        if len(_filtered_df) < 5:
            return None
        
        n_obs = len(_filtered_df)
        values = _filtered_df['Value'].values
        
        if n_obs >= 12:
            try:
                decomposition = seasonal_decompose(values, model='additive', period=12, extrapolate='fill_ea')
                trend = decomposition.trend.values
            except Exception:
                window = min(5, n_obs - 1 if n_obs % 2 == 0 else n_obs)
                if window < 3:
                    window = 3
                trend = savgol_filter(values, window, 2)
        else:
            window = min(5, n_obs - 1 if n_obs % 2 == 0 else n_obs)
            if window < 3:
                window = 3
            trend = savgol_filter(values, window, 2)
        
        residuals = values - trend
        
        result_df = pd.DataFrame({
            'year': _filtered_df['year'].values,
            'Actual': values,
            'Trend': trend,
            'Residuals': residuals
        })
        return result_df
    except Exception as e:
        st.error(f"Decomposition Error: {str(e)}")
        return None

# Trend Decomposition Plotting Function
def plot_decomposition(_decomp_df, title):
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=_decomp_df['year'],
        y=_decomp_df['Actual'],
        mode='lines+markers',
        name='Actual Data',
        line=dict(color='blue', width=2),
        marker=dict(size=5)
    ))
    
    fig.add_trace(go.Scatter(
        x=_decomp_df['year'],
        y=_decomp_df['Trend'],
        mode='lines',
        name='Trend',
        line=dict(color='red', width=3, dash='dash'),
        opacity=0.8
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="year",
        yaxis_title="Energy Value",
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    return fig

# Residuals Plotting Function
def plot_residuals(_decomp_df, title):
    fig = go.Figure()
    colors = ['red' if x < 0 else 'green' for x in _decomp_df['Residuals']]
    
    fig.add_trace(go.Bar(
        x=_decomp_df['year'],
        y=_decomp_df['Residuals'],
        name='Residuals',
        marker=dict(color=colors, line=dict(width=0))
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
    
    fig.update_layout(
        title=title,
        xaxis_title="year",
        yaxis_title="Residual Value",
        hovermode='x',
        template='plotly_white',
        height=400,
        showlegend=False
    )
    return fig

# CAGR Calculation Function
def calculate_growth_rates(_energy_df, product_name, activity_name):
    try:
        if product_name == 'Renewables':
            primary_pivot = _energy_df[
                (_energy_df['Product'] == 'Primary energy') &
                (_energy_df['Activity'] == activity_name)
            ].pivot_table(index='year', columns='Country', values='Value', aggfunc='mean')
            non_renew_pivot = _energy_df[
                (_energy_df['Product'] == 'Non-renewable energy') &
                (_energy_df['Activity'] == activity_name)
            ].pivot_table(index='year', columns='Country', values='Value', aggfunc='mean')
            pivot_df = primary_pivot - non_renew_pivot
        else:
            df = _energy_df[
                (_energy_df['Product'] == product_name) &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            pivot_df = df.pivot_table(index='year', columns='Country', values='Value', aggfunc='mean')
        
        if len(pivot_df) == 0:
            return None
        
        years = len(pivot_df) - 1
        cagr_dict = {}
        
        for country in pivot_df.columns:
            valid_data = pivot_df[country].dropna()
            if len(valid_data) >= 2:
                start_val = valid_data.iloc[0]
                end_val = valid_data.iloc[-1]
                if start_val > 0:
                    cagr = ((end_val / start_val) ** (1 / years) - 1) * 100
                    cagr_dict[country] = cagr
        
        cagr_df = pd.DataFrame(list(cagr_dict.items()), columns=['Country', 'CAGR (%)'])
        cagr_df = cagr_df.sort_values('CAGR (%)', ascending=False)
        return cagr_df
    except Exception as e:
        st.error(f"Error calculating growth rates: {str(e)}")
        return None

# CAGR Plotting Function
def plot_cagr(cagr_df, title):
    fig = px.bar(
        cagr_df,
        x='CAGR (%)',
        y='Country',
        orientation='h',
        title=title,
        color='CAGR (%)',
        color_continuous_scale='RdYlGn',
    )
    
    fig.add_vline(x=0, line_dash="dash", line_color="black", opacity=0.5)
    fig.update_layout(
        template='plotly_white',
        height=500,
        yaxis={'categoryorder': 'total ascending'}
    )
    return fig

# Multi-Country Data Preparation Function
@st.cache_data
def get_multicountry_data(_energy_df, product_name, activity_name):
    try:
        if product_name == 'Renewables':
            primary_data = _energy_df[
                (_energy_df['Product'] == 'Primary energy') &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            non_renew_data = _energy_df[
                (_energy_df['Product'] == 'Non-renewable energy') &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            primary_pivot = primary_data.pivot_table(index='year', columns='Country', values='Value', aggfunc='mean')
            non_renew_pivot = non_renew_data.pivot_table(index='year', columns='Country', values='Value', aggfunc='mean')
            result = primary_pivot - non_renew_pivot
        else:
            df = _energy_df[
                (_energy_df['Product'] == product_name) &
                (_energy_df['Activity'] == activity_name)
            ].copy()
            result = df.pivot_table(index='year', columns='Country', values='Value', aggfunc='mean')
        
        return result.reset_index()
    except Exception as e:
        st.error(f"Error getting multicountry data: {str(e)}")
        return None

# Multi-Country Comparison Plotting Function
def plot_multicountry_comparison(_data_df, selected_countries, title):
    fig = go.Figure()
    
    for country in selected_countries:
        if country in _data_df.columns:
            fig.add_trace(go.Scatter(
                x=_data_df['year'],
                y=_data_df[country],
                mode='lines+markers',
                name=country,
                hovertemplate=f'{country} - year: %{{x}} Value: %{{y:.2f}}'
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title="year",
        yaxis_title="Energy Value",
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    return fig
###
# Main Application
###
def main():
    engine = get_db_connection()
    
    with st.sidebar:
        st.markdown("### Energy & Weather Analysis")

        page = st.radio(
            "Select Tab:",
            ["Energy Analysis", "Correlation Analysis"]
        )
    # Energy Analysis Page
    if page == "Energy Analysis":
        st.title("Energy Production Analysis")
        
        if engine is None:
            st.error("Cannot connect to database")
            return
        
        energy_df = load_energy_from_db(engine)
        if energy_df is None or len(energy_df) == 0:
            st.error("No energy data available")
            return
        
        analysis_tab = st.radio(
            "Select Analysis Type:",
            ["Data Overview", "ARIMA Forecast", "Advanced Analysis"],
            horizontal=True
        )
        # Data Overview Tab
        if analysis_tab == "Data Overview":
            st.markdown("### Select Data to Analyze:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                countries = sorted(energy_df['Country'].dropna().unique())
                selected_country = st.selectbox("Country:", countries)
                country_data = energy_df[energy_df['Country'] == selected_country]
            
            with col2:
                products = sorted(country_data['Product'].dropna().unique())
                products_with_renewables = sorted(set(list(products) + ['Renewables']))
                selected_product = st.selectbox("Product:", products_with_renewables)
                
                if selected_product == 'Renewables':
                    product_data = energy_df[
                        energy_df['Product'].isin(['Primary energy', 'Non-renewable energy'])
                    ]
                else:
                    product_data = country_data[country_data['Product'] == selected_product]
            
            with col3:
                activities = sorted(product_data['Activity'].dropna().unique())
                selected_activity = st.selectbox("Activity:", activities)
            
            if selected_product == 'Renewables':
                primary_df = energy_df[
                    (energy_df['Country'] == selected_country) &
                    (energy_df['Product'] == 'Primary energy') &
                    (energy_df['Activity'] == selected_activity)
                ].sort_values('year').copy()
                
                non_renew_df = energy_df[
                    (energy_df['Country'] == selected_country) &
                    (energy_df['Product'] == 'Non-renewable energy') &
                    (energy_df['Activity'] == selected_activity)
                ].sort_values('year').copy()
                
                renewables_db_df = energy_df[
                    (energy_df['Country'] == selected_country) &
                    (energy_df['Product'] == 'Renewables') &
                    (energy_df['Activity'] == selected_activity)
                ].sort_values('year').copy()
                
                if len(primary_df) == 0 or len(non_renew_df) == 0:
                    st.warning("No data for selected filters")
                    return
                
                filtered_df = primary_df.copy()
                filtered_df['Value'] = filtered_df['Value'].values - non_renew_df['Value'].values
                filtered_df['Product'] = 'Renewables'
                
                if len(renewables_db_df) > 0 and selected_country in ['Poland', 'Lithuania', 'Czechia']:
                    filtered_df['Value'] = renewables_db_df['Value'].values
            else:
                filtered_df = energy_df[
                    (energy_df['Country'] == selected_country) &
                    (energy_df['Product'] == selected_product) &
                    (energy_df['Activity'] == selected_activity)
                ].sort_values('year').copy()
            
            if len(filtered_df) == 0:
                st.warning("No data for selected filters")
                return
            
            fig = px.line(
                filtered_df,
                x='year',
                y='Value',
                title=f"{selected_product} - {selected_activity} ({selected_country})",
                markers=True,
                labels={'Value': f'Value ({filtered_df["Unit"].iloc[0]})', 'year': 'year'}
            )
            fig.update_layout(hovermode='x unified', template='plotly_white', height=500)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("### Data Table:")
            st.dataframe(
                filtered_df[['year', 'Product', 'Activity', 'Value', 'Unit']],
                use_container_width=True
            )
            
    
            st.markdown("### Statistics:")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Min Value", f"{filtered_df['Value'].min():.2f}")
            with col2:
                st.metric("Max Value", f"{filtered_df['Value'].max():.2f}")
            with col3:
                st.metric("Avg Value", f"{filtered_df['Value'].mean():.2f}")
            with col4:
                st.metric("Std Dev", f"{filtered_df['Value'].std():.2f}")

        # ARIMA Forecast Tab
        elif analysis_tab == "ARIMA Forecast":
            st.markdown("### Select Data for Forecast:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                countries = sorted(energy_df['Country'].dropna().unique())
                selected_country_arima = st.selectbox("Country:", countries, key="arima_country")
                country_data_arima = energy_df[energy_df['Country'] == selected_country_arima]
            
            with col2:
                products_arima = sorted(country_data_arima['Product'].dropna().unique())
                products_arima_with_renewables = sorted(set(list(products_arima) + ['Renewables']))
                selected_product_arima = st.selectbox("Product:", products_arima_with_renewables, key="arima_product")
                
                if selected_product_arima == 'Renewables':
                    product_data_arima = energy_df[
                        energy_df['Product'].isin(['Primary energy', 'Non-renewable energy'])
                    ]
                else:
                    product_data_arima = country_data_arima[country_data_arima['Product'] == selected_product_arima]
            
            with col3:
                activities_arima = sorted(product_data_arima['Activity'].dropna().unique())
                selected_activity_arima = st.selectbox("Activity:", activities_arima, key="arima_activity")
            
            if selected_product_arima == 'Renewables':
                primary_df_arima = energy_df[
                    (energy_df['Country'] == selected_country_arima) &
                    (energy_df['Product'] == 'Primary energy') &
                    (energy_df['Activity'] == selected_activity_arima)
                ].sort_values('year').copy()
                
                non_renew_df_arima = energy_df[
                    (energy_df['Country'] == selected_country_arima) &
                    (energy_df['Product'] == 'Non-renewable energy') &
                    (energy_df['Activity'] == selected_activity_arima)
                ].sort_values('year').copy()
                
                renewables_db_df_arima = energy_df[
                    (energy_df['Country'] == selected_country_arima) &
                    (energy_df['Product'] == 'Renewables') &
                    (energy_df['Activity'] == selected_activity_arima)
                ].sort_values('year').copy()
                
                if len(primary_df_arima) == 0 or len(non_renew_df_arima) == 0:
                    st.warning("No data for selected filters")
                    return
                
                filtered_df_arima = primary_df_arima.copy()
                filtered_df_arima['Value'] = filtered_df_arima['Value'].values - non_renew_df_arima['Value'].values
                
                if len(renewables_db_df_arima) > 0 and selected_country_arima in ['Poland', 'Lithuania', 'Czechia']:
                    filtered_df_arima['Value'] = renewables_db_df_arima['Value'].values
            else:
                filtered_df_arima = energy_df[
                    (energy_df['Country'] == selected_country_arima) &
                    (energy_df['Product'] == selected_product_arima) &
                    (energy_df['Activity'] == selected_activity_arima)
                ].sort_values('year').copy()
            
            if len(filtered_df_arima) == 0:
                st.warning("No data for selected filters")
                return
            
    
            st.markdown("### ARIMA Time Series Forecast")
            
            col1, col2 = st.columns(2)
            
            with col1:
                forecast_years = st.slider("Forecast years ahead:", 1, 5, 3)
            
            forecast_df, model_fitted = forecast_arima(filtered_df_arima, forecast_years)
            
            if forecast_df is not None:
                fig_forecast = plot_forecast(
                    filtered_df_arima,
                    forecast_df,
                    filtered_df_arima["Unit"].iloc[0]
                )
                st.plotly_chart(fig_forecast, use_container_width=True)
                
                st.markdown("### Forecast Values (95% Confidence Interval):")
                forecast_display = forecast_df.copy()
                forecast_display['Forecast'] = forecast_display['Forecast'].apply(lambda x: f"{x:.2f}")
                forecast_display['Lower_CI'] = forecast_display['Lower_CI'].apply(lambda x: f"{x:.2f}")
                forecast_display['Upper_CI'] = forecast_display['Upper_CI'].apply(lambda x: f"{x:.2f}")
                st.dataframe(forecast_display, use_container_width=True)
            else:
                st.warning("Not enough data for ARIMA forecast (minimum 15 years required)")
        
        # Advanced Analysis Tab
        elif analysis_tab == "Advanced Analysis":
            st.title("Advanced Time Series Analysis")
            
            adv_tab = st.radio(
                "Select Analysis:",
                ["Trend Decomposition", "Multi-Country Comparison"],
                horizontal=True,
                key="adv_tab"
            )
            # Trend Decomposition Tab
            if adv_tab == "Trend Decomposition":
                st.markdown("### Trend Decomposition (Trend + Residuals)")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    countries = sorted(energy_df['Country'].dropna().unique())
                    selected_country_trend = st.selectbox("Country:", countries, key="trend_country")
                    country_data_trend = energy_df[energy_df['Country'] == selected_country_trend]
                
                with col2:
                    products_trend = sorted(country_data_trend['Product'].dropna().unique())
                    products_trend_with_renewables = sorted(set(list(products_trend) + ['Renewables']))
                    selected_product_trend = st.selectbox("Product:", products_trend_with_renewables, key="trend_product")
                    
                    if selected_product_trend == 'Renewables':
                        product_data_trend = energy_df[
                            energy_df['Product'].isin(['Primary energy', 'Non-renewable energy'])
                        ]
                    else:
                        product_data_trend = country_data_trend[country_data_trend['Product'] == selected_product_trend]
                
                with col3:
                    activities_trend = sorted(product_data_trend['Activity'].dropna().unique())
                    selected_activity_trend = st.selectbox("Activity:", activities_trend, key="trend_activity")
                
                if selected_product_trend == 'Renewables':
                    primary_df_trend = energy_df[
                        (energy_df['Country'] == selected_country_trend) &
                        (energy_df['Product'] == 'Primary energy') &
                        (energy_df['Activity'] == selected_activity_trend)
                    ].sort_values('year').copy()
                    
                    non_renew_df_trend = energy_df[
                        (energy_df['Country'] == selected_country_trend) &
                        (energy_df['Product'] == 'Non-renewable energy') &
                        (energy_df['Activity'] == selected_activity_trend)
                    ].sort_values('year').copy()
                    
                    renewables_db_df_trend = energy_df[
                        (energy_df['Country'] == selected_country_trend) &
                        (energy_df['Product'] == 'Renewables') &
                        (energy_df['Activity'] == selected_activity_trend)
                    ].sort_values('year').copy()
                    
                    if len(primary_df_trend) == 0 or len(non_renew_df_trend) == 0:
                        st.warning("No data for selected filters")
                        return
                    
                    filtered_df_trend = primary_df_trend.copy()
                    filtered_df_trend['Value'] = filtered_df_trend['Value'].values - non_renew_df_trend['Value'].values
                    
                    if len(renewables_db_df_trend) > 0 and selected_country_trend in ['Poland', 'Lithuania', 'Czechia']:
                        filtered_df_trend['Value'] = renewables_db_df_trend['Value'].values
                else:
                    filtered_df_trend = energy_df[
                        (energy_df['Country'] == selected_country_trend) &
                        (energy_df['Product'] == selected_product_trend) &
                        (energy_df['Activity'] == selected_activity_trend)
                    ].sort_values('year').copy()
                
                if len(filtered_df_trend) >= 5:
            
                    decomp_df = decompose_trend(filtered_df_trend)
                    
                    if decomp_df is not None:
                        tab_decomp1, tab_decomp2 = st.tabs(["Trend Analysis", "Residuals"])
                        
                        with tab_decomp1:
                            fig_decomp = plot_decomposition(
                                decomp_df,
                                f"Trend: {selected_product_trend} - {selected_activity_trend} ({selected_country_trend})"
                            )
                            st.plotly_chart(fig_decomp, use_container_width=True)
                            
                            st.markdown("#### Trend Direction:")
                            trend_change = decomp_df['Trend'].iloc[-1] - decomp_df['Trend'].iloc[0]
                            st.success(f"""
                            **Direction:** {"📈 Growing" if trend_change > 0 else "📉 Declining"}
                            **Total Change:** {trend_change:+.2f}
                            **Period:** {int(decomp_df['year'].min())} → {int(decomp_df['year'].max())}
                            """)
                        
                        with tab_decomp2:
                            fig_resid = plot_residuals(
                                decomp_df,
                                f"Residuals: {selected_product_trend} - {selected_activity_trend}"
                            )
                            st.plotly_chart(fig_resid, use_container_width=True)
                            
                            st.markdown("#### Residuals Analysis:")
                            st.info(f"""
                            **Average:** {decomp_df['Residuals'].mean():.6f}
                            **Volatility (Std Dev):** {decomp_df['Residuals'].std():.6f}
                            """)
                else:
                    st.warning("At least 5 years of data required for trend decomposition")

            # Multi-Country Comparison Tab
            elif adv_tab == "Multi-Country Comparison":
                st.markdown("### Multi-Country Comparison & Growth Rates")                
                col1, col2 = st.columns(2)
                
                with col1:
                    products = sorted(energy_df['Product'].dropna().unique())
                    products = [p for p in products if 'Electricity' not in p]
                    products = sorted(set(list(products) + ['Renewables']))
                    selected_product_multi = st.selectbox("Select Energy Product:", products, key="multi_product")
                
                with col2:
                    if selected_product_multi == 'Renewables':
                        activities = sorted(energy_df[
                            energy_df['Product'].isin(['Primary energy', 'Non-renewable energy'])
                        ]['Activity'].dropna().unique())
                    else:
                        product_data = energy_df[energy_df['Product'] == selected_product_multi]
                        activities = sorted(product_data['Activity'].dropna().unique())
                    
                    selected_activity_multi = st.selectbox("Select Activity:", activities, key="multi_activity")
                
                multi_data = get_multicountry_data(energy_df, selected_product_multi, selected_activity_multi)
                
                if multi_data is not None and len(multi_data) > 0:
                    available_countries = [col for col in multi_data.columns if col != 'year']
                    selected_countries_multi = st.multiselect(
                        "Select Countries to Compare:",
                        options=available_countries,
                        default=available_countries[:min(6, len(available_countries))],
                        key="multi_countries"
                    )
                    
                    if len(selected_countries_multi) > 0:
                
                        tab_comp1, tab_comp2 = st.tabs(["Trends Comparison", "Growth Rates (CAGR)"])
                        
                        with tab_comp1:
                            fig_multi = plot_multicountry_comparison(
                                multi_data,
                                selected_countries_multi,
                                f"{selected_product_multi} - {selected_activity_multi} (Multi-Country Trends)"
                            )
                            st.plotly_chart(fig_multi, use_container_width=True)
                        
                        with tab_comp2:
                            cagr_df = calculate_growth_rates(energy_df, selected_product_multi, selected_activity_multi)
                            
                            if cagr_df is not None and len(cagr_df) > 0:
                                fig_cagr = plot_cagr(
                                    cagr_df,
                                    f"CAGR (1980-2023): {selected_product_multi} - {selected_activity_multi}"
                                )
                                st.plotly_chart(fig_cagr, use_container_width=True)
                                
                                st.markdown("### Growth Rates Ranking:")
                                st.dataframe(cagr_df.reset_index(drop=True), use_container_width=True)
                    else:
                        st.info("Select at least 1 country to compare")
                else:
                    st.warning("No data available for selected filters")
    # Correlation Analysis Page
    elif page == "Correlation Analysis":
        st.title("Correlation Analysis")
        
        if engine is None:
            st.error("Cannot connect to database")
            return
        
        energy_df = load_energy_from_db(engine)
        if energy_df is None or len(energy_df) == 0:
            st.error("No energy data available")
            return
        
        analysis_type = st.radio(
            "Select Analysis:",
            ["Weather Correlation", "Cross-Country Comparison", "Import/Export Correlation"],
            horizontal=True
        )
        # Weather Correlation Analysis
        if analysis_type == "Weather Correlation":
            weather_df = load_weather_from_db(engine)
            st.markdown("### Weather vs Energy Production Correlation (Poland)")
            
            if weather_df is None or len(weather_df) == 0:
                st.error("No weather data available")
                return
            
            try:
                poland_energy = energy_df[energy_df['Country'] == 'Poland'].copy()
                if len(poland_energy) == 0:
                    st.error("No energy data for Poland")
                    return
                
                poland_energy["Product_Activity"] = (
                    poland_energy["Product"].astype(str) + " | " + poland_energy["Activity"].astype(str)
                )
                
                energy_pivot = (
                    poland_energy
                    .groupby(["year", "Product_Activity"])["Value"]
                    .mean()
                    .unstack("Product_Activity")
                    .reset_index()
                )
                
                energy_cols = [col for col in energy_pivot.columns if col != 'year']
                production_cols = [col for col in energy_cols if 'Electricity' not in col]
                
                primary_col = 'Primary energy | Production'
                non_renew_col = 'Non-renewable energy | Production'
                
                if primary_col in production_cols and non_renew_col in production_cols:
                    energy_pivot['Renewables | Production'] = energy_pivot[primary_col] - energy_pivot[non_renew_col]
                    production_cols.append('Renewables | Production')
                
                production_cols_sorted = (
                    sorted([col for col in production_cols if 'Generation' not in col]) +
                    sorted([col for col in production_cols if 'Generation' in col])
                )
                
                energy_pivot = energy_pivot[['year'] + production_cols_sorted]
                
                weather_avg = (
                    weather_df
                    .groupby("year")[["Temperature", "Humidity_Percent", "WindSpeed", "Cloudiness"]]
                    .mean()
                    .reset_index()
                    .rename(columns={
                        "year": "year",
                        "Humidity_Percent": "Humidity",
                        "WindSpeed": "Wind_Speed"
                    })
                )
                
                merged = pd.merge(energy_pivot, weather_avg, on="year", how="inner")
                
                for col in production_cols_sorted:
                    merged[col] = merged[col].replace(0, np.nan)
                
                if len(merged) == 0:
                    st.error("No overlapping data")
                    return
                
                weather_factors = ['Temperature', 'Humidity', 'Wind_Speed', 'Cloudiness']
                corr_cols = weather_factors + production_cols_sorted
                
                corr_matrix = merged[corr_cols].corr()
                weather_energy_corr = corr_matrix.loc[weather_factors, production_cols_sorted]
                
                fig_corr = go.Figure(
                    data=go.Heatmap(
                        z=weather_energy_corr.values,
                        x=weather_energy_corr.columns,
                        y=weather_energy_corr.index,
                        colorscale="RdBu",
                        zmid=0,
                        colorbar=dict(title="Correlation"),
                        text=np.round(weather_energy_corr.values, 2),
                        texttemplate="%{text:.2f}",
                        textfont={"size": 10}
                    )
                )
                
                fig_corr.update_layout(
                    title="Weather vs Energy Production Correlation (Poland)",
                    height=600,
                    yaxis=dict(title="Weather Factors"),
                    xaxis=dict(title="Energy Series", tickangle=-45),
                    template='plotly_white'
                )
                
                st.plotly_chart(fig_corr, use_container_width=True)
                
                # Scatter Plot with Trend Line
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_energy = st.selectbox("Select energy type:", production_cols_sorted, index=0)
                
                with col2:
                    selected_weather = st.selectbox("Select weather factor:", weather_factors, index=0)
                
                plot_data = merged[['year', selected_energy, selected_weather]].dropna()
                
                if len(plot_data) == 0:
                    st.warning("No data for selected options")
                else:
                    correlation = plot_data[selected_energy].corr(plot_data[selected_weather])
                    
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=plot_data[selected_weather],
                        y=plot_data[selected_energy],
                        mode='markers',
                        name='Data Points',
                        marker=dict(size=8, color='blue', opacity=0.6),
                        text=plot_data['year'],
                        hovertemplate='year: %{text}<br>' + f'{selected_weather}: %{{x:.2f}}<br>' + f'{selected_energy}: %{{y:.2f}}'
                    ))
                    
                    z_trend = np.polyfit(plot_data[selected_weather].values, plot_data[selected_energy].values, 1)
                    p_trend = np.poly1d(z_trend)
                    weather_range = np.linspace(plot_data[selected_weather].min(), plot_data[selected_weather].max(), 100)
                    
                    fig.add_trace(go.Scatter(
                        x=weather_range,
                        y=p_trend(weather_range),
                        mode='lines',
                        name='Trend Line',
                        line=dict(color='red', width=2, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title=f"{selected_weather} -> {selected_energy} | Corr: {correlation:.3f}",
                        xaxis_title=selected_weather,
                        yaxis_title=selected_energy,
                        hovermode='closest',
                        height=500,
                        template='plotly_white'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
            
            except Exception as e:
                st.error(f"Error: {str(e)}")

        # Cross-Country Comparison Analysis
        elif analysis_type == "Cross-Country Comparison":
            st.markdown("### Cross-Country Comparison")
            col1, col2 = st.columns(2)
            
            with col1:
                products = sorted(energy_df['Product'].dropna().unique())
                products = [p for p in products if 'Electricity' not in p]
                products = sorted(set(list(products) + ['Renewables']))
                selected_product = st.selectbox("Select Energy Product:", products, key="cc_product")
            
            with col2:
                if selected_product == 'Renewables':
                    activities = sorted(energy_df[
                        energy_df['Product'].isin(['Primary energy', 'Non-renewable energy'])
                    ]['Activity'].dropna().unique())
                else:
                    product_data = energy_df[energy_df['Product'] == selected_product]
                    activities = sorted(product_data['Activity'].dropna().unique())
                
                selected_activity = st.selectbox("Select Activity:", activities, key="cc_activity")
            
            if selected_product == 'Renewables':
                countries_available = sorted(energy_df[
                    energy_df['Product'].isin(['Primary energy', 'Non-renewable energy']) &
                    (energy_df['Activity'] == selected_activity)
                ]['Country'].dropna().unique())
            else:
                countries_available = sorted(energy_df[
                    (energy_df['Product'] == selected_product) &
                    (energy_df['Activity'] == selected_activity)
                ]['Country'].dropna().unique())
            
            if len(countries_available) == 0:
                st.warning(f"No data for {selected_product} - {selected_activity}")
            else:
                selected_countries = st.multiselect(
                    "Select Countries to Compare:",
                    options=countries_available,
                    default=countries_available[:min(5, len(countries_available))],
                    key="cc_countries"
                )
                
                if len(selected_countries) >= 2:
                    try:
                        country_data = prepare_country_energy_data(energy_df, selected_product, selected_activity)
                        
                        if country_data is not None and len(country_data) > 0:
                            available_cols = ['year']
                            for c in selected_countries:
                                if c in country_data.columns:
                                    available_cols.append(c)
                            
                            country_data_filtered = country_data[available_cols]
                            common_years = country_data_filtered.dropna().shape[0]
                            
                            st.caption(f"Common years with data for all selected countries: {common_years}")
                            
                            transformation_mode = st.radio(
                                "Value type for correlation:",
                                ["Levels", "year-to-year change", "Log change"],
                                horizontal=True
                            )
                            
                            df_transformed = transform_data(country_data_filtered, transformation_mode, selected_countries)
                            
                    
                            tab1, tab2, tab3 = st.tabs(["Heatmap", "Rolling Correlation", "Data"])
                            
                            with tab1:
                                corr_matrix = calculate_country_correlations(df_transformed, selected_countries)
                                
                                if corr_matrix is not None:
                                    fig_heatmap = create_correlation_heatmap(
                                        corr_matrix,
                                        f"{selected_product} - {selected_activity} ({transformation_mode})"
                                    )
                                    st.plotly_chart(fig_heatmap, use_container_width=True)
                            
                            with tab2:
                                if len(selected_countries) >= 2:
                                    c1 = st.selectbox("Country 1", selected_countries, index=0, key="rolling_c1")
                                    c2 = st.selectbox("Country 2", selected_countries, index=1 if len(selected_countries) > 1 else 0, key="rolling_c2")
                                    window = st.slider("Rolling window (years)", 3, 15, 7)
                                    
                                    roll_corr = create_rolling_correlation(df_transformed, c1, c2, window)
                                    
                                    if roll_corr is not None:
                                        roll_corr_df = roll_corr.reset_index()
                                        roll_corr_df.columns = ['year', 'Correlation']
                                        
                                        fig_roll = px.line(
                                            roll_corr_df,
                                            x="year",
                                            y="Correlation",
                                            title=f"Rolling Correlation ({window}-year window): {c1} vs {c2}"
                                        )
                                        
                                        fig_roll.update_layout(
                                            template="plotly_white",
                                            yaxis=dict(range=[-1, 1]),
                                            height=500
                                        )
                                        
                                        st.plotly_chart(fig_roll, use_container_width=True)
                                    else:
                                        st.warning("Not enough data for rolling correlation")
                            
                            with tab3:
                                st.dataframe(df_transformed, use_container_width=True)
                                st.download_button(
                                    "Download CSV",
                                    df_transformed.to_csv(index=False),
                                    f"cross_country_{selected_product.replace(' ', '_')}.csv",
                                    "text/csv"
                                )
                        else:
                            st.error("No data available")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                else:
                    st.warning("Select at least 2 countries")
                    
        # Import/Export Correlation Analysis
        elif analysis_type == "Import/Export Correlation":
            st.markdown("### Import/Export Correlation Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                countries = sorted(energy_df['Country'].dropna().unique())
                country1 = st.selectbox("Exporting Country:", countries, key="ie_country1")
            
            with col2:
                country2 = st.selectbox("Importing Country:", countries, key="ie_country2")
            
            selected_product = "Electricity"
            
            if country1 == country2:
                st.warning("Select different countries for export and import")
            else:
                try:
            
                    st.markdown("#### Lag Analysis (All Correlations)")
                    
                    lag_corrs = create_lagged_correlation_matrix(energy_df, country1, country2, selected_product, max_lag=5)
                    
                    if lag_corrs and len(lag_corrs) > 0:
                        lag_df = pd.DataFrame({
                            'Lag (years)': list(lag_corrs.keys()),
                            'Correlation': list(lag_corrs.values())
                        })
                        
                        fig_lag = px.bar(
                            lag_df,
                            x='Lag (years)',
                            y='Correlation',
                            title=f"Correlation by Import Lag: {country1} Export -> {country2} Import",
                            labels={'Correlation': 'Pearson Correlation', 'Lag (years)': 'Years Lagged'},
                            text='Correlation'
                        )
                        
                        fig_lag.update_traces(texttemplate='%{text:.3f}', textposition='outside')
                        fig_lag.update_layout(
                            template='plotly_white',
                            height=400,
                            yaxis=dict(range=[-1, 1])
                        )
                        
                        st.plotly_chart(fig_lag, use_container_width=True)
                        
                        best_lag = max(lag_corrs, key=lambda x: abs(lag_corrs[x]))
                        best_corr = lag_corrs[best_lag]
                        
                        st.success(f"Strongest correlation at {best_lag}-year lag: {best_corr:.3f}")
                        
                
                        st.markdown(f"#### Scatter Plot (Best Lag: {best_lag} years)")
                        
                        result = create_import_export_correlation(energy_df, country1, country2, selected_product, lag=best_lag)
                        
                        if result is not None:
                            corr_value, merged_data = result
                            
                            fig_ie = go.Figure()
                            
                            fig_ie.add_trace(go.Scatter(
                                x=merged_data[f'Export_{country1}'],
                                y=merged_data[f'Import_{country2}'],
                                mode='markers',
                                name='Data Points',
                                marker=dict(size=10, color='rgba(99, 110, 250, 0.7)', line=dict(width=1, color='white')),
                                text=merged_data['year'],
                                hovertemplate='year: %{text}<br>' + f'{country1} Export: %{{x:.2f}}<br>' + f'{country2} Import: %{{y:.2f}}'
                            ))
                            
                            z_trend = np.polyfit(
                                merged_data[f'Export_{country1}'].values,
                                merged_data[f'Import_{country2}'].values,
                                1
                            )
                            p_trend = np.poly1d(z_trend)
                            export_range = np.linspace(
                                merged_data[f'Export_{country1}'].min(),
                                merged_data[f'Export_{country1}'].max(),
                                100
                            )
                            
                            fig_ie.add_trace(go.Scatter(
                                x=export_range,
                                y=p_trend(export_range),
                                mode='lines',
                                name='Trend Line',
                                line=dict(color='red', width=3, dash='dash')
                            ))
                            
                            fig_ie.update_layout(
                                title=f"{country1} Export -> {country2} Import (Lag: {best_lag}y) | Corr: {corr_value:.3f}",
                                xaxis_title=f"Exports from {country1}",
                                yaxis_title=f"Imports to {country2}",
                                height=500,
                                template='plotly_white',
                                hovermode='closest'
                            )
                            
                            st.plotly_chart(fig_ie, use_container_width=True)
                            st.info(f"Data Points: {len(merged_data)} overlapping years")
                        else:
                            st.warning("No data available for selected countries and product")
                    else:
                        st.warning("No data available for selected countries and product")
                except Exception as e:
                    st.error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
