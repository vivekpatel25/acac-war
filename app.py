import pandas as pd
import streamlit as st
from pathlib import Path
from pandas.errors import EmptyDataError

st.set_page_config(page_title="ACAC Net Points Leaderboard", layout="wide")
DATA_DIR = Path("data")

st.markdown("""
### 🏀 The Best ACAC Basketball Players in Overall Net Points
_Updated weekly — last update:_ **Sun Oct 19 2025**

These rankings show total offensive and defensive net points contributed by each player,  
based on team point differential while they were on the court.  
Negative defensive values indicate points allowed, positive offensive values indicate scoring impact.
""")

tab1, tab2 = st.tabs(["Men", "Women"])

def load(g):
    f = DATA_DIR / f"leaderboard_{g}_2025.csv"
    if not f.exists(): return pd.DataFrame()
    return pd.read_csv(f)

def render(df):
    if df.empty:
        st.warning("No data yet.")
        return

    df = df.rename(columns={
        "player_name":"Player",
        "team_name":"Team",
        "games":"G",
        "minutes":"MIN",
        "offense":"Offense",
        "defense":"Defense",
        "overall":"Overall"
    })

    df = df[["Player","Team","G","MIN","Offense","Defense","Overall"]]

    st.dataframe(
        df.style
        .background_gradient(subset=["Offense"], cmap="Reds")
        .background_gradient(subset=["Defense"], cmap="Greens_r")  # inverse for negatives
        .background_gradient(subset=["Overall"], cmap="Greys"),
        use_container_width=True,
        hide_index=True
    )

with tab1:
    render(load("men"))

with tab2:
    render(load("women"))

