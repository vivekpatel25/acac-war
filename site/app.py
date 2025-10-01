import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="ACAC Net-pts WAR", layout="wide")
st.title("ACAC Net-pts WAR (oWAR / dWAR / tWAR) — Season Leaderboard")

SEASON = 2025
data_path = Path(__file__).parent / f"leaderboard_{SEASON}.csv"

@st.cache_data
def load():
    if data_path.exists():
        return pd.read_csv(data_path)
    else:
        st.warning("No leaderboard found yet. Run `python compute/compute_war.py` to generate it.")
        return pd.DataFrame()

df = load()
if df.empty:
    st.stop()

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

styled = dfv[show_cols].rename(columns=ren).style \
    .background_gradient(subset=[labels[0]], cmap="Reds") \
    .background_gradient(subset=[labels[1]], cmap="Greens") \
    .background_gradient(subset=[labels[2]], cmap="Greys")

st.dataframe(styled, use_container_width=True, hide_index=True)
st.caption("oNet/dNet/tNet are per-100 possessions vs league average. WAR converts Net Points vs replacement into wins added.")
