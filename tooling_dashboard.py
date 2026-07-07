import streamlit as st
import pandas as pd
import plotly.express as px

# Set page configuration
st.set_page_config(
    page_title="PACCAR Tooling Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a cleaner dashboard look
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-label {
        font-size: 1rem;
        color: #6c757d;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f8f9fa;
        border-radius: 4px 4px 0 0;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e9ecef;
        border-bottom: 3px solid #1f77b4;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    """
    Reads multiple CSV or Excel files, identifies the correct header row,
    consolidates them, and cleans data types.
    """
    if not uploaded_files:
        return pd.DataFrame()

    dfs = []
    for file in uploaded_files:
        file_ext = file.name.split('.')[-1].lower()
        try:
            if file_ext == 'csv':
                # Decode lines to find the actual header row
                lines = file.getvalue().decode("utf-8").splitlines()
                header_row = 0
                for i, line in enumerate(lines):
                    if "Tooling ID" in line and "Plant Name" in line:
                        header_row = i
                        break
                
                # Reset pointer and read
                file.seek(0)
                df = pd.read_csv(file, skiprows=header_row)
                dfs.append(df)
            elif file_ext in ['xls', 'xlsx']:
                # Read first few rows to find header
                preview_df = pd.read_excel(file, nrows=20, header=None)
                header_row = 0
                for idx, row in preview_df.iterrows():
                    # Safely convert all values to string to avoid float join errors
                    row_str = ' '.join([str(val) for val in row.values])
                    if "Tooling ID" in row_str and "Plant Name" in row_str:
                        header_row = idx
                        break
                
                # Reset pointer and read
                file.seek(0)
                df = pd.read_excel(file, skiprows=header_row)
                dfs.append(df)
                
        except Exception as e:
            st.error(f"Error processing {file.name}: {str(e)}")

    if dfs:
        # Concatenate all files
        master_df = pd.concat(dfs, ignore_index=True)
        
        # Drop empty rows
        master_df = master_df.dropna(subset=['Tooling ID', 'Plant Name'], how='all')

        # Clean numerical columns
        num_cols = [
            'Accumulated Shots (life-to-date)',
            'Rated Life (shots)',
            'Life Consumed %',
            'Week 27 Shot Count',
            'Week 27 Part Count',
            'Week 27 Uptime (hrs)'
        ]
        
        for col in num_cols:
            if col in master_df.columns:
                master_df[col] = pd.to_numeric(
                    master_df[col].astype(str).str.replace(',', ''), 
                    errors='coerce'
                ).fillna(0)
                
        return master_df
    return pd.DataFrame()


def main():
    st.title("⚙️ PACCAR OEM Asset Management & Production Dashboard")
    st.markdown("Top-level visibility into tooling lifecycles, supplier sensor compliance, and highest-volume production assets.")

    # --- SIDEBAR & FILE UPLOAD ---
    with st.sidebar:
        st.header("1. Data Import")
        uploaded_files = st.file_uploader(
            "Upload Tooling Data (CSV, XLS, XLSX)", 
            type=["csv", "xls", "xlsx"], 
            accept_multiple_files=True
        )
        st.divider()

    # Load Data
    with st.spinner("Processing data files..."):
        df = process_uploaded_files(uploaded_files)

    if df.empty:
        st.info("👈 Please upload your tooling data extracts from the sidebar to populate the dashboard.")
        return

    # --- SIDEBAR FILTERS ---
    st.sidebar.header("2. Segment & Filter")
    
    # 0. Global Text Search
    search_query = st.sidebar.text_input(
        "🔍 Search Tool/Part", 
        "", 
        placeholder="Enter Tool ID or Part Name..."
    )
    
    # 1. Supplier / Plant Filter
    plant_options = sorted(df["Plant Name"].dropna().unique().tolist())
    selected_plants = st.sidebar.multiselect("🏭 Supplier / Plant Location", plant_options, default=plant_options)
    
    # 2. Project / Part ID Filter
    project_options = sorted(df["Part ID"].dropna().astype(str).unique().tolist())
    selected_projects = st.sidebar.multiselect("📁 Project / Part ID", project_options, placeholder="Select to filter (defaults to All)")
    if not selected_projects:
        selected_projects = project_options

    # 3. Part Name / Tool Type Filter
    part_options = sorted(df["Part Name"].dropna().astype(str).unique().tolist())
    selected_parts = st.sidebar.multiselect("🗜️ Part Name / Tool Type", part_options, placeholder="Select to filter (defaults to All)")
    if not selected_parts:
        selected_parts = part_options

    # 4. Status Filters
    eol_options = sorted(df["EOL Status"].dropna().unique().tolist())
    selected_eol = st.sidebar.multiselect("⚠️ EOL Status", eol_options, default=eol_options)
    
    sensor_options = sorted(df["Sensor Status"].dropna().unique().tolist())
    selected_sensors = st.sidebar.multiselect("📡 Sensor Status", sensor_options, default=sensor_options)

    # 5. Life Consumed Filter
    min_life, max_life = float(df["Life Consumed %"].min()), float(df["Life Consumed %"].max())
    if min_life == max_life:
        min_life, max_life = 0.0, max_life + 1.0

    life_consumed_range = st.sidebar.slider(
        "⏳ Life Consumed % Range", 
        min_value=0.0, 
        max_value=max_life, 
        value=(0.0, max_life),
        step=0.1
    )

    # Apply Baseline Filters
    filtered_df = df[
        (df["Plant Name"].isin(selected_plants)) &
        (df["Part ID"].astype(str).isin(selected_projects)) &
        (df["Part Name"].astype(str).isin(selected_parts)) &
        (df["EOL Status"].isin(selected_eol)) &
        (df["Sensor Status"].isin(selected_sensors)) &
        (df["Life Consumed %"] >= life_consumed_range[0]) &
        (df["Life Consumed %"] <= life_consumed_range[1])
    ]

    # Apply Text Search Filter (if used)
    if search_query:
        search_lower = search_query.lower()
        # Allows searching across Tooling ID, Part ID, and Part Name simultaneously
        filtered_df = filtered_df[
            filtered_df["Tooling ID"].fillna('').astype(str).str.lower().str.contains(search_lower) |
            filtered_df["Part ID"].fillna('').astype(str).str.lower().str.contains(search_lower) |
            filtered_df["Part Name"].fillna('').astype(str).str.lower().str.contains(search_lower)
        ]

    # --- KPI SNAPSHOT ---
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Tools in Scope</div>
                <div class="metric-value">{len(filtered_df):,}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with kpi2:
        past_eol = len(filtered_df[filtered_df["EOL Status"] == "Past EOL"])
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Assets Past EOL</div>
                <div class="metric-value" style="color:#d62728;">{past_eol:,}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with kpi3:
        total_shots = int(filtered_df["Week 27 Shot Count"].sum())
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Weekly Production (Shots)</div>
                <div class="metric-value">{total_shots:,}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with kpi4:
        # Calculate overall sensor connectivity %
        online_count = len(filtered_df[filtered_df["Sensor Status"] == "Online"])
        connectivity_rate = (online_count / len(filtered_df) * 100) if len(filtered_df) > 0 else 0
        color = "#2ca02c" if connectivity_rate >= 90 else "#ff7f0e" if connectivity_rate >= 75 else "#d62728"
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Global Sensor Online Rate</div>
                <div class="metric-value" style="color:{color};">{connectivity_rate:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("") # Spacer

    # --- TABS LAYOUT ---
    tab1, tab2, tab3 = st.tabs([
        "📊 Production & Utilization", 
        "📡 Asset Health & Compliance", 
        "📋 Full Master Data View"
    ])

    # =========================================================
    # TAB 1: PRODUCTION METRICS & UTILIZATION
    # =========================================================
    with tab1:
        st.subheader("Production Volume & Asset Utilization (Week 27)")
        col1, col2 = st.columns(2)

        with col1:
            # Top 10 Producing Tools (Bar)
            top_producers = filtered_df.nlargest(10, 'Week 27 Shot Count')
            if not top_producers.empty:
                top_producers['Label'] = top_producers['Tooling ID'].astype(str) + " (" + top_producers['Plant Name'] + ")"
                
                fig_top_shots = px.bar(
                    top_producers, x='Week 27 Shot Count', y='Label', 
                    orientation='h', title="Highest Volume Assets (Top 10 by Shot Count)",
                    hover_data=["Part Name", "Life Consumed %"],
                    color='Week 27 Shot Count', color_continuous_scale='Blues'
                )
                fig_top_shots.update_layout(yaxis={'categoryorder':'total ascending'}, yaxis_title="")
                st.plotly_chart(fig_top_shots, use_container_width=True)
                
                # Corresponding Data Table
                st.caption("Data: Highest Volume Assets")
                st.dataframe(
                    top_producers[['Tooling ID', 'Plant Name', 'Part ID', 'Part Name', 'Week 27 Shot Count', 'Life Consumed %']],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No production data available for current filters.")

        with col2:
            # Top 10 Uptime Tools (Bar)
            top_uptime = filtered_df.nlargest(10, 'Week 27 Uptime (hrs)')
            if not top_uptime.empty:
                top_uptime['Label'] = top_uptime['Tooling ID'].astype(str) + " (" + top_uptime['Plant Name'] + ")"
                
                fig_top_uptime = px.bar(
                    top_uptime, x='Week 27 Uptime (hrs)', y='Label', 
                    orientation='h', title="Highest Utilized Assets (Top 10 by Production Hours)",
                    hover_data=["Part Name", "Week 27 Shot Count"],
                    color='Week 27 Uptime (hrs)', color_continuous_scale='Teal'
                )
                fig_top_uptime.update_layout(yaxis={'categoryorder':'total ascending'}, yaxis_title="")
                fig_top_uptime.add_vline(x=168, line_dash="dash", line_color="red", annotation_text="Max 168 Hrs/Wk")
                st.plotly_chart(fig_top_uptime, use_container_width=True)
                
                # Corresponding Data Table
                st.caption("Data: Highest Utilized Assets")
                st.dataframe(
                    top_uptime[['Tooling ID', 'Plant Name', 'Part ID', 'Part Name', 'Week 27 Uptime (hrs)', 'Week 27 Shot Count']],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No uptime data available for current filters.")


    # =========================================================
    # TAB 2: ASSET HEALTH & COMPLIANCE
    # =========================================================
    with tab2:
        st.subheader("Asset Health, Tooling Lifecycle & Supplier Connectivity")
        col3, col4 = st.columns(2)

        with col3:
            # EOL Status Breakdown (Donut)
            eol_counts = filtered_df["EOL Status"].value_counts().reset_index()
            eol_counts.columns = ["EOL Status", "Tool Count"]
            color_map = {"Healthy": "#2ca02c", "Warning": "#ff7f0e", "Past EOL": "#d62728"}
            
            fig_eol = px.pie(
                eol_counts, names="EOL Status", values="Tool Count",
                title="Overall Asset Health (End of Life Status)",
                color="EOL Status", color_discrete_map=color_map, hole=0.4
            )
            fig_eol.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_eol, use_container_width=True)
            
            # Corresponding Data Table
            st.caption("Data: EOL Status Distribution")
            st.dataframe(eol_counts, use_container_width=True, hide_index=True)

        with col4:
            # Sensor Online Rate per Supplier (Bar)
            if len(filtered_df) > 0:
                sensor_rate = filtered_df.groupby('Plant Name').agg(
                    Total_Tools=('Sensor Status', 'count'),
                    Online_Tools=('Sensor Status', lambda x: (x == 'Online').sum()),
                    Online_Rate_Pct=('Sensor Status', lambda x: (x == 'Online').mean() * 100)
                ).reset_index()
                sensor_rate = sensor_rate.sort_values('Online_Rate_Pct', ascending=True)

                fig_sensor = px.bar(
                    sensor_rate, x='Online_Rate_Pct', y='Plant Name', 
                    orientation='h', title="Sensor Connectivity Rate by Supplier",
                    text_auto='.1f'
                )
                fig_sensor.update_layout(xaxis_range=[0, 100], xaxis_title="Online Rate (%)", yaxis_title="")
                fig_sensor.update_traces(marker_color=['#d62728' if val < 85 else '#1f77b4' for val in sensor_rate['Online_Rate_Pct']])
                st.plotly_chart(fig_sensor, use_container_width=True)
                
                # Corresponding Data Table
                st.caption("Data: Sensor Connectivity Rates")
                sensor_rate_display = sensor_rate.copy()
                sensor_rate_display['Online_Rate_Pct'] = sensor_rate_display['Online_Rate_Pct'].apply(lambda x: f"{x:.1f}%")
                sensor_rate_display.columns = ["Supplier / Plant", "Total Tools", "Online Tools", "Online Rate (%)"]
                st.dataframe(sensor_rate_display, use_container_width=True, hide_index=True)


    # =========================================================
    # TAB 3: MASTER DATA VIEW
    # =========================================================
    with tab3:
        st.subheader("Itemized Asset Master List")
        st.markdown("Filter, sort, and search specific tools across your entire portfolio. Columns are customizable.")
        
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "Life Consumed %": st.column_config.NumberColumn("Life Consumed %", format="%.2f%%"),
                "Accumulated Shots (life-to-date)": st.column_config.NumberColumn("Accumulated Shots", format="%d"),
                "Rated Life (shots)": st.column_config.NumberColumn("Rated Life", format="%d"),
                "Week 27 Shot Count": st.column_config.NumberColumn("Wk 27 Shots", format="%d"),
                "Week 27 Uptime (hrs)": st.column_config.NumberColumn("Wk 27 Uptime", format="%.1f hrs")
            }
        )

        # Export functionality
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Master Data Extract (CSV)",
            data=csv,
            file_name='paccar_asset_master_export.csv',
            mime='text/csv',
        )

if __name__ == "__main__":
    main()