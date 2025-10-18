import pandas as pd
import streamlit as st
from pathlib import Path
from pandas.errors import EmptyDataError

st.set_page_config(page_title="ACAC Player Ratings", layout="wide")
st.title("ACAC Player Efficiency Ratings — Season 2025")

SEASON = 2025

# Resolve paths relative to this app file (works on Railway & locally)
REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"

MEN_FILE = DATA_DIR / f"leaderboard_men_{SEASON}.csv"
WOMEN_FILE = DATA_DIR / f"leaderboard_women_{SEASON}.csv"

@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.warning(f"⚠️ Missing file: `{path}`")
        return pd.DataFrame()
    if path.stat().st_size == 0:
        st.warning(f"⚠️ Empty file: `{path.name}`")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        st.warning(f"⚠️ `{path.name}` is empty or unreadable.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to read `{path.name}`: {e}")
        return pd.DataFrame()

# Gender toggle
gender = st.radio("Select Division", ["Men", "Women"], index=0, horizontal=True)
data_path = MEN_FILE if gender == "Men" else WOMEN_FILE

df = load_csv(data_path)

# Show helpful diagnostics if something is off
if df.empty:
    st.info(
        "No leaderboard yet. Make sure you generated it with "
        "`python compute/compute_rtg.py` and that the file exists at:\n\n"
        f"`{data_path}`\n\n"
        "Minimal header required:\n"
        "`player_id,player_name,team_name,pos,class,poss_for,OffRtg_on,DefRtg_on,tRtg,season`"
    )
    st.stop()

# ---- Column hygiene / fallbacks ----
# Normalize column names that sometimes differ
rename_map = {
    "TEAM": "team_name",
    "Team": "team_name",
    "team": "team_name",
    "PLAYER": "player_name",
    "Player": "player_name",
    "OffRtg": "OffRtg_on",
    "DefRtg": "DefRtg_on",
    "Total": "tRtg",
    "total": "tRtg",
}
df.rename(columns=rename_map, inplace=True)

# If team_name is missing but team_id exists, clone it.
if "team_name" not in df.columns and "team_id" in df.columns:
    df["team_name"] = df["team_id"]

# If still missing, show columns and stop gracefully
required = {"player_name","team_name","poss_for","OffRtg_on","DefRtg_on","tRtg"}
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(
        "CSV is missing required columns.\n\n"
        f"Missing: {missing}\n\n"
        f"Found columns: {list(df.columns)}\n\n"
        "Fix your compute export or adjust headers to match."
    )
    st.stop()

# ---- Filters ----
c1, c2, c3 = st.columns(3)
teams = ["All"] + sorted(df["team_name"].dropna().unique().tolist())
positions = ["All"] + sorted(df["pos"].dropna().astype(str).unique().tolist()) if "pos" in df.columns else ["All"]
classes = ["All"] + sorted(df["class"].dropna().astype(str).unique().tolist()) if "class" in df.columns else ["All"]

team = c1.selectbox("Team", teams, index=0)
pos  = c2.selectbox("Position", positions, index=0)
cls  = c3.selectbox("Class", classes, index=0)

dfv = df.copy()
if team != "All": dfv = dfv[dfv["team_name"] == team]
if pos  != "All" and "pos" in dfv.columns: dfv = dfv[dfv["pos"] == pos]
if cls  != "All" and "class" in dfv.columns: dfv = dfv[dfv["class"] == cls]

# ---- Sorting ----
sort_choice = st.radio("Sort By", ["OffRtg_on", "DefRtg_on", "tRtg"], horizontal=True)
ascending = True if sort_choice == "DefRtg_on" else False
dfv = dfv.sort_values(sort_choice, ascending=ascending)

# ---- Table ----
show_cols = ["player_name","team_name","poss_for","OffRtg_on","DefRtg_on","tRtg"]
if "pos" in dfv.columns: show_cols.insert(2, "pos")
if "class" in dfv.columns: show_cols.insert(3, "class")

ren = {
    "player_name": "PLAYER",
    "team_name": "TEAM",
    "pos": "POS",
    "class": "CLASS",
    "poss_for": "POSS",
    "OffRtg_on": "OFF RTG",
    "DefRtg_on": "DEF RTG",
    "tRtg": "TOTAL RTG",
}

st.dataframe(dfv[show_cols].rename(columns=ren), use_container_width=True, hide_index=True)
st.caption(
    "OffRtg = points scored per 100 possessions • "
    "DefRtg = points allowed per 100 (lower is better) • "
    "Total = OffRtg + |DefRtg|."
)
