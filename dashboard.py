import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION ---
API_BASE_URL = "http://localhost:8000/api/v1" 
st.set_page_config(page_title="Equal Property AI | Analytics", layout="wide")

# --- DATA FETCHING ---
@st.cache_data(ttl=300)
def get_api_data(endpoint):
    try:
        r = requests.get(f"{API_BASE_URL}/{endpoint}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error ({endpoint}): {e}")
        return None

# --- DASHBOARD UI ---
st.title("🏢 Equal Property AI - Command Center")

# --- MODULE 1: PORTFOLIO VIEW (WITHOUT PROPERTY_ID) ---
# Purpose: High-level executive summary of all assets
st.header("🌍 Global Portfolio Performance")
portfolio_summary = get_api_data("analytics/portfolio-summary")

if portfolio_summary:
    data = portfolio_summary.get("portfolio_health", [])
    df_p = pd.DataFrame(data)
    
    # KPIs for the whole portfolio
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Avg Portfolio Occupancy", f"{df_p['occupancy_rate'].mean():.1f}%")
    kpi2.metric("Assets At Risk", len(df_p[df_p['status'] == 'At Risk']))
    kpi3.metric("Total Managed Assets", len(df_p))

    # Portfolio Distribution Chart
    fig_portfolio = px.bar(
        df_p, x='property_name', y='occupancy_rate', color='status',
        color_discrete_map={'Healthy': '#00CC96', 'At Risk': '#EF553B'},
        title="Portfolio Occupancy Distribution",
        template="plotly_white"
    )
    st.plotly_chart(fig_portfolio, use_container_width=True, key="global_portfolio_chart")
else:
    st.info("Global portfolio data is currently unavailable.")

st.divider()

# --- MODULE 2: PROPERTY FILTER (USING PROPERTY_ID) ---
# Purpose: Granular audit and momentum analysis for a specific asset
st.header("🔍 Property Specific Analytics")

# Step 1: Get all properties from momentum endpoint to populate the filter
momentum_data = get_api_data("analytics/leasing-momentum")

if momentum_data:
    # Use a dictionary to map Names to IDs for the filter
    # Based on your FastAPI logic, we find property_id inside the nested 'data'
    prop_map = {p['property_name']: p['data'][0]['property_id'] for p in momentum_data}
    selected_prop_name = st.selectbox("Select Property to Audit:", list(prop_map.keys()))
    selected_id = prop_map[selected_prop_name]

    # Step 2: Display Momentum & Early Warnings for the filtered ID
    prop_details = next(item for item in momentum_data if item["property_name"] == selected_prop_name)
    df_m = pd.DataFrame(prop_details['data'])
    df_m['month'] = pd.to_datetime(df_m['month'])

    col_meta, col_chart = st.columns([1, 2])
    
    with col_meta:
        st.subheader("Asset Status")
        st.write(f"**Momentum:** {prop_details['momentum_status']}")
        st.write(f"**Continuous Decline:** {'Yes 🚨' if prop_details['assets_with_continuous_decline'] else 'No'}")
        
        if prop_details['early_warning_flags']:
            st.warning("⚠️ Flags: " + ", ".join(prop_details['early_warning_flags']))

    with col_chart:
        # Physical vs Economic Occupancy Trend
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=df_m['month'], y=df_m['physical_occupancy_pct'], name="Physical %", line=dict(color='#636EFA')))
        fig_trend.add_trace(go.Scatter(x=df_m['month'], y=df_m['economic_occupancy_pct'], name="Economic %", line=dict(dash='dash', color='#00CC96')))
        fig_trend.update_layout(title=f"Occupancy Trends: {selected_prop_name}", height=300, margin=dict(t=30, b=0))
        st.plotly_chart(fig_trend, use_container_width=True, key=f"trend_{selected_id}")

    # Step 3: Unit Audit for the filtered ID
    st.subheader(f"Unit Vacancy Audit (ID: {selected_id})")
    unit_audit = get_api_data(f"analytics/unit-audit/{selected_id}")
    
    if unit_audit:
        df_audit = pd.DataFrame(unit_audit)
        
        # Financial Impact KPI
        potential_rev = df_audit['MarketRentEstimate'].sum()
        st.error(f"Monthly Revenue Leakage: **${potential_rev:,.2f}** across {len(df_audit)} vacant units")
        
        # Raw Audit Table
        st.dataframe(df_audit, use_container_width=True)
    else:
        st.success("Operational Excellence: No vacant units found for this property.")
else:
    st.warning("Please ensure the FastAPI server is running to use property filters.")