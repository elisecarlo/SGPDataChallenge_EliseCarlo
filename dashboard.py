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

def parse_course_xml(xml_file = r"E:\SailGP\SGPDataChallenge_EliseCarlo\Data\Race_XMLs\25011905_03-13-55.xml"):
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
# 1. Upload et concaténation de plusieurs fichiers CSV
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
    # Extraction du boat_name depuis le nom du fichier (ex: data_MyBoat.csv → MyBoat)
    boat_name = uploaded_file.name.replace("data_", "").replace(".csv", "").strip()
    df_temp = pd.read_csv(uploaded_file)
    df_temp["boat_name"] = boat_name
    df_list.append(df_temp)

df = pd.concat(df_list, ignore_index=True)
df["Tack"] = np.where(df["AWA_SGP_deg"] > 0, "Starboard", "Port")
file_names = [uploaded_file.name for uploaded_file in uploaded_files]
st.write("Uploaded files: " + ", ".join(file_names))

# =============================================================================
# 2. Conversion et filtrage temporel de base
# =============================================================================
df["DATETIME"] = pd.to_datetime(df["DATETIME"])
start_dt = df["DATETIME"].min()
end_dt = df["DATETIME"].max()

# On peut garder ici un filtrage global (par date et heure) si besoin :
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

# =============================================================================
# 3. Sélection rapide des bateaux et autres filtres (via la sidebar)
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

# Attribution d'une couleur unique à chaque bateau
available_colors = px.colors.qualitative.Plotly
boat_colors = {boat: available_colors[i % len(available_colors)] for i, boat in enumerate(sorted(df["boat_name"].unique()))}

# =============================================================================
# 4. Carte avec slider animé
# =============================================================================
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Boat Positions with Full Track")

    # Initialisation des variables de session pour gérer l'animation du slider
    if "is_playing" not in st.session_state:
        st.session_state.is_playing = False
    if "current_time" not in st.session_state:
        st.session_state.current_time = start_datetime

    # Slider animé pour la sélection du temps
    current_time = st.slider(
        "Select Time",
        min_value=start_datetime,
        max_value=end_datetime,
        value=st.session_state.current_time,
        format="YYYY-MM-DD HH:mm:ss",
        step=datetime.timedelta(seconds=10)
    )

    # Bouton Play/Pause pour animer le slider
    play_pause_col1, play_pause_col2 = st.columns([0.1, 0.9])
    with play_pause_col1:
        if st.button("▶️" if not st.session_state.is_playing else "⏸️"):
            st.session_state.is_playing = not st.session_state.is_playing

    # Animation du slider (avance automatique si "Play" est actif)
    if st.session_state.is_playing:
        if current_time < end_datetime:
            st.session_state.current_time += datetime.timedelta(seconds=10)
        else:
            st.session_state.is_playing = False  # Arrêter si on atteint la fin

    # Création de la carte avec les parcours et positions actuelles
    fig_map = go.Figure()

    for boat in selected_boats:
        boat_df = df[df["boat_name"] == boat]
        
        # Tracé complet de la course
        fig_map.add_trace(go.Scattermapbox(
            lat=boat_df["LATITUDE_GPS_unk"],
            lon=boat_df["LONGITUDE_GPS_unk"],
            mode="lines",
            line=dict(width=1, color=boat_colors[boat]),
            name=f"{boat} Track",
            hoverinfo="skip"  # On évite d'afficher chaque point du tracé
        ))

        # Filtrage pour ne garder que la position au temps actuel
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
        # Ajout des marques (points de parcours)
    # Chargement des données du parcours
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

    # Ajout des boundaries (polygone)
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


    # Mise à jour du layout
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
    # Sélection du bateau pour lequel afficher le dashboard
    dashboard_boat = st.selectbox("Select Boat for Dashboard", options=selected_boats)
    dashboard_df = df[df["boat_name"] == dashboard_boat]
    dashboard_df = dashboard_df[dashboard_df["DATETIME"] <= current_time]
    if not dashboard_df.empty:
        current_record = dashboard_df.iloc[-1]
    else:
        current_record = None

    # Liste des variables disponibles pour le dashboard
    dashboard_var_options = dashboard_df.columns.tolist()   
    st.markdown("### Dashboard Variables")
    # Création d'une grille 2 colonnes x 3 lignes (6 cellules)
    for row in range(3):
        cols = st.columns(2)
        for col_index in range(2):
            cell_index = row * 2 + col_index
            with cols[col_index]:
                # Menu déroulant pour choisir la variable à afficher dans la cellule
                selected_var = st.selectbox(f"Variable {cell_index+1}", dashboard_var_options, key=f"dash_{cell_index}")
                if current_record is not None and selected_var in current_record:
                    value = current_record[selected_var]
                else:
                    value = "No data"
                st.metric(label=selected_var, value=value)

# =============================================================================
# 5. (Optionnel) Autres visualisations, par exemple un graphique de type "line"
# =============================================================================
st.subheader("Variable over Time")
y_variable_options = df.columns.tolist()
selected_y_variable = st.selectbox("Select variable for Y-axis", y_variable_options)
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
# Visualisation : Wind Speed and Direction
# =============================================================================
st.subheader("Wind Speed and Direction")
fig_wind = px.scatter(
    df, 
    x="TWS_SGP_km_h_1", 
    y="TWD_SGP_deg", 
    color="boat_name", 
    color_discrete_map=boat_colors,
    title="Wind Speed vs. Wind Direction",
    labels={
        "TWS_SGP_km_h_1": "True Wind Speed (km/h)",
        "TWD_SGP_deg": "True Wind Direction (°)",
        "boat_name": "Boat"
    }
)
st.plotly_chart(fig_wind, use_container_width=True)



st.write("Course Marks", race_course)