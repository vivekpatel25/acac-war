import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import date, timedelta

st.set_page_config(page_title="ACAC Net-pts WAR", layout="wide")

# --- Gender Toggle ---
gender = st.radio("Select League", ["Men", "Women"], horizontal=True)

# --- Season Settings ---
SEASON = 2025
data_file = f"leaderboard_{gender.lower()}_{SEASON}.csv"
data_path = Path(__file__).parent / "data" / data_file

@st.cache_data
def load(file):
    if file.exists():
        return pd.read_csv(file)
    else:
        st.warning(f"No leaderboard found yet for {gender}. Run compute script to generate it.")
        return pd.DataFrame()

df = load(data_path)
if df.empty:
    st.stop()

# --- Header Section (ESPN style) ---
today = date.today()
last_monday = today - timedelta(days=today.weekday())
updated_str = last_monday.strftime("%a %b %d %Y")

st.markdown(
    f"""
    <h1 style="text-align:center;">The Best ACAC {gender} Players in Wins Above Replacement (WAR)</h1>
    <p style="text-align:center; color:grey; font-size:16px;">
        Updated through {updated_str}
    </p>
    <p style="text-align:center; font-size:16px;">
        These are updated weekly and based on the Net Points metric, which says how much better or worse than average a player is, then converted to Wins.
    </p>
    <h3 style="text-align:center;">Where Every ACAC {gender} Player Stands</h3>
    <p style="text-align:center;">WAR from offense, defense and overall</p>
    """,
    unsafe_allow_html=True
)

# --- Filters ---
c1, c2, c3, c4 = st.columns(4)
teams = ["All"] + sorted(df["team_name"].dropna().unique().tolist())
positions = ["All"] + sorted([x for x in df["pos"].dropna().unique().tolist() if x])
classes = ["All"] + sorted([x for x in df["class"].dropna().unique().tolist() if x])

season = c1.selectbox("Season", [SEASON], index=0)
team = c2.selectbox("Team", teams, index=0)
pos  = c3.selectbox("Position", positions, index=0)
cls  = c4.selectbox("Class", classes, index=0)

# --- Metric View ---
metric_mode = st.radio("Metric View", ["WAR", "Net Points / 80 Poss", "Net Points (per-100)"], horizontal=True)

dfv = df.copy()
if team != "All": dfv = dfv[dfv.team_name == team]
if pos  != "All": dfv = dfv[dfv.pos == pos]
if cls  != "All": dfv = dfv[dfv["class"] == cls]

# --- Derive display columns by mode ---
if metric_mode == "WAR":
    o_col, d_col, t_col = "oWAR", "dWAR", "tWAR"
    labels = ("oWAR","dWAR","tWAR")
elif metric_mode == "Net Points / 80 Poss":
    dfv["oNP80"] = dfv["oNet"] * (80/100)
    dfv["dNP80"] = dfv["dNet"] * (80/100)
    dfv["tNP80"] = dfv["oNP80"] + dfv["dNP80"]
    o_col, d_col, t_col = "oNP80","dNP80","tNP80"
    labels = ("oNet/80","dNet/80","tNet/80")
else:
    o_col, d_col, t_col = "oNet","dNet","tNet"
    labels = ("oNet","dNet","tNet")

# --- ESPN-style Sort Buttons ---
sort_choice = st.segmented_control("SORT TABLE:", ["Offense","Defense","Total"], default="Total")
order_col = {"Offense": o_col, "Defense": d_col, "Total": t_col}[sort_choice]
dfv = dfv.sort_values(order_col, ascending=False)

# --- Display Leaderboard with Coloring ---
show_cols = ["player_name","team_name","pos","class","G", o_col, d_col, t_col]
ren = {"player_name":"PLAYER","team_name":"TEAM","pos":"POS","class":"CLASS","G":"GAMES",
       o_col:labels[0], d_col:labels[1], t_col:labels[2]}

# lock color scale across dataset (like ESPN)
max_owar = df[o_col].max() if o_col in df else None
max_dwar = df[d_col].max() if d_col in df else None
max_twar = df[t_col].max() if t_col in df else None

styled = dfv[show_cols].rename(columns=ren).style
if max_owar: styled = styled.background_gradient(subset=[labels[0]], cmap="Reds", vmin=0, vmax=max_owar)
if max_dwar: styled = styled.background_gradient(subset=[labels[1]], cmap="Greens", vmin=0, vmax=max_dwar)
if max_twar: styled = styled.background_gradient(subset=[labels[2]], cmap="Greys", vmin=0, vmax=max_twar)

st.dataframe(styled, use_container_width=True, hide_index=True)
st.caption("oNet/dNet/tNet are per-100 possessions vs league average. WAR converts Net Points vs replacement into wins added.")
