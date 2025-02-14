import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import datetime
import os
from bs4 import BeautifulSoup
import numpy as np
import warnings
from pathlib import Path

# =============================================================================
# Running command: streamlit run /Your/repesetory/dashboard.py
# =============================================================================

def parse_course_xml(xml_file = r"Data\Race_XMLs\25011905_03-13-55.xml"):
    #xml_file = next((os.path.join(xml_dir, f) for f in os.listdir(xml_dir) if f.startswith(f"{race_num:08d}")), None)
    """if xml_file is None:
        raise FileNotFoundError(f"Aucun fichier XML trouvé pour la course {race_num}.")"""
    
    with open(xml_file, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "lxml-xml")

    race_course = {}
    for compound_mark in soup.find_all("CompoundMark"):
        marks = compound_mark.find_all("Mark")
        lat, lon = np.mean([float(m.get("TargetLat")) for m in marks]), np.mean([float(m.get("TargetLng")) for m in marks])
        race_course[compound_mark.get("CompoundMarkID")] = (compound_mark.get("Name"), lat, lon)
    
    boundary_coords = [(float(limit.get("Lon")), float(limit.get("Lat"))) for limit in soup.find("CourseLimit", {"name": "Boundary"}).find_all("Limit")]
    return race_course, boundary_coords

warnings.filterwarnings('ignore')

st.set_page_config(page_title="SGP Boat Logs Analysis", page_icon=":sailboat:", layout="wide")
st.title(":sailboat: SGP Boat Logs Data Analysis")
st.markdown('<style>div.block-container{padding-top:1rem;}</style>', unsafe_allow_html=True)

# =============================================================================
# 1. Boat logs upload
# =============================================================================
uploaded_files = st.file_uploader(
    ":file_folder: Upload one or more Boat Logs CSV files", 
    type=["csv"], 
    accept_multiple_files=True
)
if not uploaded_files:
    st.stop()

df_list = []
for uploaded_file in uploaded_files:
    # boat_name extraction
    boat_name = uploaded_file.name.replace("data_", "").replace(".csv", "").strip()
    df_temp = pd.read_csv(uploaded_file)
    df_temp["boat_name"] = boat_name
    df_list.append(df_temp)

df = pd.concat(df_list, ignore_index=True)
df["Tack"] = np.where(df["AWA_SGP_deg"] > 0, "Starboard", "Port")
file_names = [uploaded_file.name for uploaded_file in uploaded_files]
st.write("Uploaded files: " + ", ".join(file_names))

# =============================================================================
# 2. Datetime filtering
# =============================================================================
df["DATETIME"] = pd.to_datetime(df["DATETIME"])
start_dt = df["DATETIME"].min()
end_dt = df["DATETIME"].max()

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", start_dt.date())
    start_time = st.time_input("Start Time", start_dt.time())
with col2:
    end_date = st.date_input("End Date", end_dt.date())
    end_time = st.time_input("End Time", end_dt.time())

start_datetime = datetime.datetime.combine(start_date, start_time)
end_datetime = datetime.datetime.combine(end_date, end_time)

df = df[(df["DATETIME"] >= start_datetime) & (df["DATETIME"] <= end_datetime)].copy()
# Filtrage par "Tack" avec la possibilité de ne pas choisir de tack
tack_options = ["All"] + sorted(df["Tack"].unique().tolist())
selected_tack = st.selectbox("Tack selection", tack_options)
if selected_tack != "All":
    df = df[df["Tack"] == selected_tack]
# =============================================================================
# 3. Boat & filters selection
# =============================================================================
boat_options = sorted(df["boat_name"].unique())
selected_boats = st.sidebar.multiselect("Select Boat(s) to Analyze", options=boat_options, default=boat_options)
if selected_boats:
    df = df[df["boat_name"].isin(selected_boats)]
else:
    st.warning("No boat selected. Please select at least one boat.")
    st.stop()

st.sidebar.header("Choose additional filters:")
if "TRK_RACE_NUM_unk" in df.columns:
    race_numbers = st.sidebar.multiselect("Pick your Race Number", df["TRK_RACE_NUM_unk"].unique())
    if race_numbers:
        df = df[df["TRK_RACE_NUM_unk"].isin(race_numbers)]
if "TRK_LEG_NUM_unk" in df.columns:
    leg_numbers = st.sidebar.multiselect("Pick your Leg Number", df["TRK_LEG_NUM_unk"].unique())
    if leg_numbers:
        df = df[df["TRK_LEG_NUM_unk"].isin(leg_numbers)]
if "BOAT_SPEED_km_h_1" in df.columns:
    min_speed, max_speed = st.sidebar.slider(
        "Boat Speed (km/h)", 
        float(df["BOAT_SPEED_km_h_1"].min()), 
        float(df["BOAT_SPEED_km_h_1"].max()), 
        (float(df["BOAT_SPEED_km_h_1"].min()), float(df["BOAT_SPEED_km_h_1"].max()))
    )
    df = df[(df["BOAT_SPEED_km_h_1"] >= min_speed) & (df["BOAT_SPEED_km_h_1"] <= max_speed)]

available_colors = px.colors.qualitative.Plotly
boat_colors = {boat: available_colors[i % len(available_colors)] for i, boat in enumerate(sorted(df["boat_name"].unique()))}

# =============================================================================
# 4. Map with animated slider
# =============================================================================
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Boat Positions with Full Track")
    #Time slider
    if "is_playing" not in st.session_state:
        st.session_state.is_playing = False
    if "current_time" not in st.session_state:
        st.session_state.current_time = start_datetime

    current_time = st.slider(
        "Select Time",
        min_value=start_datetime,
        max_value=end_datetime,
        value=st.session_state.current_time,
        format="YYYY-MM-DD HH:mm:ss",
        step=datetime.timedelta(seconds=10)
    )

    # Play/Pause button (need to be improved)
    play_pause_col1, play_pause_col2 = st.columns([0.1, 0.9])
    with play_pause_col1:
        if st.button("▶️" if not st.session_state.is_playing else "⏸️"):
            st.session_state.is_playing = not st.session_state.is_playing

    # Slider animation
    if st.session_state.is_playing:
        if current_time < end_datetime:
            st.session_state.current_time += datetime.timedelta(seconds=10)
        else:
            st.session_state.is_playing = False

    # Map creation
    fig_map = go.Figure()

    for boat in selected_boats:
        boat_df = df[df["boat_name"] == boat]
        
        # Boats tracking
        fig_map.add_trace(go.Scattermapbox(
            lat=boat_df["LATITUDE_GPS_unk"],
            lon=boat_df["LONGITUDE_GPS_unk"],
            mode="lines",
            line=dict(width=1, color=boat_colors[boat]),
            name=f"{boat} Track"
        ))

        # Filtering to get current position
        boat_current_df = boat_df[boat_df["DATETIME"] <= current_time]
        if not boat_current_df.empty:
            current_record = boat_current_df.iloc[-1]  # Dernière position connue

            fig_map.add_trace(go.Scattermapbox(
                lat=[current_record["LATITUDE_GPS_unk"]],
                lon=[current_record["LONGITUDE_GPS_unk"]],
                mode="markers",
                marker=dict(size=15, color=boat_colors[boat]),
                name=f"{boat} Current Position",
                hovertext=f"{boat}<br>{current_record['DATETIME']}",
                hoverinfo="text"
            ))

    # Race marks
    race_course, boundary_coords = parse_course_xml()
    for mark_id, (mark_name, lat, lon) in race_course.items():
        fig_map.add_scattermapbox(
            lat=[lat],
            lon=[lon],
            mode="markers+text",
            marker=dict(size=10, color="red"),
            text=[mark_name],
            textposition="top right",
            showlegend=False
        )

    # Boundaries (not working yet)
    if boundary_coords:
        lats, lons = zip(*boundary_coords)
        #st.write(f"Polygone : {lats[0]} - {lats[-1]} - {lons[0]} - {lons[-1]}")
        #st.write(boundary_coords)
        fig_map.add_scattermapbox(
            lat=lats + (lats[0],),  # Fermer le polygone
            lon=lons + (lons[0],),            
            mode="lines",
            line=dict(width=6, color="blue"),
            name="Boundary"
        )
        #st.write(f"lat {lat}, lon {lon}")


    # Layout update
    fig_map.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(
            center={"lat": df["LATITUDE_GPS_unk"].mean(), "lon": df["LONGITUDE_GPS_unk"].mean()},
            zoom=14
        ),
        margin={"r": 0, "t": 30, "l": 0, "b": 0}
    )

    st.plotly_chart(fig_map, use_container_width=True)



with col_right:
    st.subheader("Boat Dashboard")
    # Boat selection for the dashboard
    dashboard_boat = st.selectbox("Select Boat for Dashboard", options=selected_boats)
    dashboard_df = df[df["boat_name"] == dashboard_boat]
    dashboard_df = dashboard_df[dashboard_df["DATETIME"] <= current_time]
    if not dashboard_df.empty:
        current_record = dashboard_df.iloc[-1]
    else:
        current_record = None

    # Availables vars for the dashboard
    dashboard_var_options = dashboard_df.columns.tolist()   
    st.markdown("### Dashboard Variables")
    
    for row in range(3):
        cols = st.columns(2)
        for col_index in range(2):
            cell_index = row * 2 + col_index
            with cols[col_index]:
                selected_var = st.selectbox(f"Variable {cell_index+1}", dashboard_var_options, key=f"dash_{cell_index}")
                if current_record is not None and selected_var in current_record:
                    value = current_record[selected_var]
                else:
                    value = "No data"
                st.metric(label=selected_var, value=value)

# =============================================================================
# 5. Time graph
# =============================================================================
st.subheader("Variable over Time")
y_variable_options = df.columns.tolist()
selected_y_variable = st.selectbox("Select variable for Y-axis", y_variable_options, index=y_variable_options.index("BOAT_SPEED_km_h_1"))
fig_speed = px.line(
    df, 
    x="DATETIME", 
    y=selected_y_variable, 
    color="boat_name", 
    color_discrete_map=boat_colors,
    title=f"{selected_y_variable} over Time"
)
st.plotly_chart(fig_speed, use_container_width=True)

# =============================================================================
# X/Y graph
# =============================================================================
# Définir les options disponibles
options = df.columns.tolist()

# Sélection des variables X et Y, côte à côte
st.subheader("X/Y graph")
col1, col2 = st.columns(2)
x_var = col1.selectbox("X variable selection", options, index=options.index("TWS_SGP_km_h_1"))
y_var = col2.selectbox("Y variable selection", options, index=options.index("TWD_SGP_deg"))



# Mise en page : Graphique à gauche, statistiques (moyennes) à droite
col_graph, col_stats = st.columns([3, 1])

with col_graph:
    fig_wind = px.scatter(
        df, 
        x=x_var, 
        y=y_var, 
        color="boat_name",
        color_discrete_map=boat_colors,
        title=f"{x_var} vs. {y_var}",
        labels={x_var: x_var, y_var: y_var, "boat_name": "Boat"},
        trendline="ols",
        height=600
    )
    st.plotly_chart(fig_wind, use_container_width=True)

with col_stats:
    st.subheader(f"Stats")

    # Sélection du bateau pour le calcul des statistiques
    boats = sorted(df["boat_name"].unique())
    selected_boat = st.selectbox("Boat selection", boats)
    
    # Filtrer le dataframe pour le bateau sélectionné
    df_boat = df[df["boat_name"] == selected_boat]
    
    # Calculer les statistiques pour chaque variable si le dataframe n'est pas vide
    if not df_boat.empty:
        # Pour x_var
        mean_x   = df_boat[x_var].mean()
        median_x = df_boat[x_var].median()
        std_x    = df_boat[x_var].std()
        min_x    = df_boat[x_var].min()
        max_x    = df_boat[x_var].max()
        
        # Pour y_var
        mean_y   = df_boat[y_var].mean()
        median_y = df_boat[y_var].median()
        std_y    = df_boat[y_var].std()
        min_y    = df_boat[y_var].min()
        max_y    = df_boat[y_var].max()
    else:
        mean_x = median_x = std_x = min_x = max_x = 0
        mean_y = median_y = std_y = min_y = max_y = 0

    # Organiser les statistiques dans deux colonnes : une pour x_var et une pour y_var
    x_stats, y_stats = st.columns(2)

    with x_stats:
        st.markdown(f"### Stats for **{x_var}**")
        st.metric(label="Mean", value=f"{mean_x:.2f}")
        st.metric(label="Median", value=f"{median_x:.2f}")
        st.metric(label="Std dev", value=f"{std_x:.2f}")
        st.metric(label="Min", value=f"{min_x:.2f}")
        st.metric(label="Max", value=f"{max_x:.2f}")

    with y_stats:
        st.markdown(f"### Stats for **{y_var}**")
        st.metric(label="Mean", value=f"{mean_y:.2f}")
        st.metric(label="Median", value=f"{median_y:.2f}")
        st.metric(label="Std dev", value=f"{std_y:.2f}")
        st.metric(label="Min", value=f"{min_y:.2f}")
        st.metric(label="Max", value=f"{max_y:.2f}")

    # Expander pour afficher un résumé descriptif complet
with st.expander("Get more stats"):
    st.write(df_boat.describe())




# =============================================================================