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
        
        # Drop empty rows (e.g., trailing commas or blank lines)
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
                # Remove commas and convert to float
                master_df[col] = pd.to_numeric(
                    master_df[col].astype(str).str.replace(',', ''), 
                    errors='coerce'
                ).fillna(0)
                
        return master_df
    return pd.DataFrame()


def main():
    st.title("⚙️ PACCAR Tooling Snapshot Dashboard")
    st.markdown("Upload your tooling data extracts to view aggregated KPIs and filter across facilities.")

    # --- SIDEBAR & FILE UPLOAD ---
    with st.sidebar:
        st.header("Data Import")
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
        st.info("👈 Please upload one or more tooling data files from the sidebar to generate the dashboard.")
        return

    # --- SIDEBAR FILTERS (Excel-like functionality) ---
    st.sidebar.header("Data Filters")
    
    # 1. Categorical Filters
    plant_options = sorted(df["Plant Name"].dropna().unique().tolist())
    selected_plants = st.sidebar.multiselect("🏭 Plant Name", plant_options, default=plant_options)
    
    eol_options = sorted(df["EOL Status"].dropna().unique().tolist())
    selected_eol = st.sidebar.multiselect("⚠️ EOL Status", eol_options, default=eol_options)
    
    sensor_options = sorted(df["Sensor Status"].dropna().unique().tolist())
    selected_sensors = st.sidebar.multiselect("📡 Sensor Status", sensor_options, default=sensor_options)

    # 2. Numerical Range Filters
    min_life, max_life = float(df["Life Consumed %"].min()), float(df["Life Consumed %"].max())
    
    # Safety fallback if min and max are the same
    if min_life == max_life:
        min_life, max_life = 0.0, max_life + 1.0

    life_consumed_range = st.sidebar.slider(
        "⏳ Life Consumed % Range", 
        min_value=0.0, 
        max_value=max_life, 
        value=(0.0, max_life),
        step=0.1
    )

    # Apply all filters
    filtered_df = df[
        (df["Plant Name"].isin(selected_plants)) &
        (df["EOL Status"].isin(selected_eol)) &
        (df["Sensor Status"].isin(selected_sensors)) &
        (df["Life Consumed %"] >= life_consumed_range[0]) &
        (df["Life Consumed %"] <= life_consumed_range[1])
    ]

    # --- KPI SNAPSHOT (TOP LEVEL) ---
    st.subheader("Top Level Snapshot")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        total_tools = len(filtered_df)
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Tools Tracked</div>
                <div class="metric-value">{total_tools:,}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with kpi2:
        past_eol = len(filtered_df[filtered_df["EOL Status"] == "Past EOL"])
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Tools Past EOL</div>
                <div class="metric-value" style="color:#d62728;">{past_eol:,}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with kpi3:
        total_shots = int(filtered_df["Week 27 Shot Count"].sum())
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Wk 27 Total Shots</div>
                <div class="metric-value">{total_shots:,}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with kpi4:
        total_uptime = round(filtered_df["Week 27 Uptime (hrs)"].sum(), 1)
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Wk 27 Total Uptime (hrs)</div>
                <div class="metric-value">{total_uptime:,.1f}</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("") # Spacer

    # --- CHARTS AND VISUALIZATIONS ---
    col1, col2 = st.columns(2)

    with col1:
        # Distribution of tools by plant
        plant_counts = filtered_df["Plant Name"].value_counts().reset_index()
        plant_counts.columns = ["Plant Name", "Tool Count"]
        fig_plants = px.bar(
            plant_counts, 
            x="Plant Name", 
            y="Tool Count",
            title="Tool Inventory by Plant",
            color="Plant Name",
            text_auto=True
        )
        fig_plants.update_layout(showlegend=False, xaxis_title="", yaxis_title="Number of Tools")
        st.plotly_chart(fig_plants, use_container_width=True)

    with col2:
        # EOL Status Breakdown
        eol_counts = filtered_df["EOL Status"].value_counts().reset_index()
        eol_counts.columns = ["EOL Status", "Count"]
        # Standardize colors if possible
        color_map = {"Healthy": "#2ca02c", "Warning": "#ff7f0e", "Past EOL": "#d62728"}
        fig_eol = px.pie(
            eol_counts, 
            names="EOL Status", 
            values="Count",
            title="End of Life (EOL) Status Breakdown",
            color="EOL Status",
            color_discrete_map=color_map,
            hole=0.4
        )
        fig_eol.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_eol, use_container_width=True)


    st.subheader("Asset Utilization vs. Lifecycle")
    # Scatter plot: Accumulated Shots vs Rated Life
    fig_scatter = px.scatter(
        filtered_df, 
        x="Accumulated Shots (life-to-date)", 
        y="Rated Life (shots)",
        color="EOL Status",
        hover_data=["Tooling ID", "Part Name", "Plant Name", "Life Consumed %"],
        title="Accumulated Shots vs. Rated Life",
        color_discrete_map={"Healthy": "#2ca02c", "Warning": "#ff7f0e", "Past EOL": "#d62728"}
    )
    # Add a 1:1 parity line to visualize 100% life consumed boundary
    max_val = max(filtered_df["Accumulated Shots (life-to-date)"].max(), filtered_df["Rated Life (shots)"].max())
    fig_scatter.add_shape(
        type="line", line=dict(dash='dash', color='gray'),
        x0=0, y0=0, x1=max_val, y1=max_val
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # --- RAW DATA TABLE ---
    st.subheader("Detailed Tooling View")
    st.markdown("Filter, sort, and search this interactive table exactly like Excel.")
    
    # Display dataframe with built-in Streamlit sorting and filtering tools
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "Life Consumed %": st.column_config.NumberColumn(
                "Life Consumed %",
                help="Percentage of rated life consumed",
                format="%.2f%%"
            ),
            "Accumulated Shots (life-to-date)": st.column_config.NumberColumn(
                "Accumulated Shots",
                format="%d"
            ),
            "Rated Life (shots)": st.column_config.NumberColumn(
                "Rated Life",
                format="%d"
            )
        }
    )

    # Optional CSV Export of filtered data
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv,
        file_name='filtered_tooling_data.csv',
        mime='text/csv',
    )

if __name__ == "__main__":
    main()