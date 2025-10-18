import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="ACAC Net Ratings Leaderboard", layout="wide")
st.title("ACAC Player Efficiency Ratings — Season 2025")

SEASON = 2025

# gender toggle
gender = st.radio("Select Division", ["Men", "Women"], horizontal=True)
data_path = Path(__file__).parent.parent / "data" / f"leaderboard_{gender.lower()}_{SEASON}.csv"

@st.cache_data
def load(file):
    if file.exists():
        return pd.read_csv(file)
    else:
        st.warning(f"No leaderboard data found for {gender}.")
        return pd.DataFrame()

df = load(data_path)
if df.empty:
    st.stop()

# Filters
c1, c2, c3 = st.columns(3)
teams = ["All"] + sorted(df["team_name"].dropna().unique().tolist())
positions = ["All"] + sorted(df["pos"].dropna().unique().tolist())
classes = ["All"] + sorted(df["class"].dropna().unique().tolist())

team = c1.selectbox("Team", teams, index=0)
pos  = c2.selectbox("Position", positions, index=0)
cls  = c3.selectbox("Class", classes, index=0)

dfv = df.copy()
if team != "All": dfv = dfv[dfv.team_name == team]
if pos  != "All": dfv = dfv[dfv.pos == pos]
if cls  != "All": dfv = dfv[dfv["class"] == cls]

# Sorting
sort_choice = st.radio("Sort By", ["OffRtg", "DefRtg", "tRtg"], horizontal=True)
dfv = dfv.sort_values(sort_choice, ascending=(sort_choice=="DefRtg"))

# Table
show_cols = ["player_name","team_name","pos","class","poss_for","OffRtg_on","DefRtg_on","tRtg"]
ren = {
    "player_name":"PLAYER",
    "team_name":"TEAM",
    "pos":"POS",
    "class":"CLASS",
    "poss_for":"POSS",
    "OffRtg_on":"OFF RTG",
    "DefRtg_on":"DEF RTG",
    "tRtg":"TOTAL RTG"
}

st.dataframe(dfv[show_cols].rename(columns=ren), use_container_width=True, hide_index=True)
st.caption("OffRtg = Points scored per 100 possessions | DefRtg = Points allowed per 100 | tRtg = OffRtg + |DefRtg| (XRAPM-style)")
