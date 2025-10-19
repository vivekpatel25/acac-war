import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="ACAC Player Ratings — Season 2025", layout="wide")

DATA_DIR = Path(__file__).resolve().parent / "data"
SEASON = 2025

def load_board(gender: str) -> pd.DataFrame:
    path = DATA_DIR / f"leaderboard_{gender}_{SEASON}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["player_name","team_name","G","Off","Def","Overall"])
    try:
        df = pd.read_csv(path)
    except Exception:
        # handle weird encodings if ever present
        df = pd.read_csv(path, encoding="latin1")
    # Ensure numeric and 1 decimal formatting
    for c in ("G","Off","Def","Overall"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

st.markdown("# ACAC Player Ratings — Season 2025")

tabs = st.tabs(["Men", "Women"])

for tab, gender in zip(tabs, ["men","women"]):
    with tab:
        df = load_board(gender)
        if df.empty or len(df) == 0:
            st.info(
                f"No leaderboard yet for **{gender}**. "
                f"Generate it with `python compute/compute_rtg.py` "
                f"and ensure the file `data/leaderboard_{gender}_{SEASON}.csv` exists."
            )
            continue

        # Display like ESPN: Player | Team | G | Offense | Defense | Overall
        df = df.rename(columns={
            "player_name":"Player",
            "team_name":"Team",
            "Off":"Offense",
            "Def":"Defense",
        })

        # Order and rounding
        cols = ["Player","Team","G","Offense","Defense","Overall"]
        df = df[cols].copy()
        df["G"] = df["G"].astype(int)
        for c in ("Offense","Defense","Overall"):
            df[c] = df[c].map(lambda x: f"{x:.1f}")

        # Use st.table to DISABLE interactive sorting on Player/Team as requested
        st.caption("Values are season totals (one decimal). Only numeric stats are meaningful for sorting; "
                   "this table is fixed to avoid sorting by Player/Team.")
        st.table(df)
