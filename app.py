import streamlit as st
import pandas as pd
from datetime import date

SEASON = 2025

st.set_page_config(
    page_title="ACAC Player Impact Ratings",
    layout="wide",
)

# --- Page Title & Description ---
st.markdown("""
# 🏀 **The Best ACAC Basketball Players — Season 2025**

_Updated automatically — last update:_ **{:%b %d, %Y}**

---

These rankings estimate each player's **overall impact** on their team's performance this ACAC season.  

---

###Note:

This model is not a pure *Wins Above Replacement (WAR)* metric but follows a similar idea —  
quantifying how much a player contributes to team success beyond an average performer.

---
""".format(date.today()))

# --- Helper: Load Leaderboards ---
@st.cache_data
def load_board(gender):
    try:
        df = pd.read_csv(f"data/leaderboard_{gender}_{SEASON}.csv")
        return df
    except Exception:
        return pd.DataFrame()

# --- Custom Styling ---
st.markdown("""
<style>
    /* Center and bold numeric columns */
    .stDataFrame td div[data-testid="stMarkdownContainer"] {
        text-align: center !important;
        font-weight: 600 !important;
    }

    /* Make headers bold and larger */
    .stDataFrame thead tr th div {
        text-align: center !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
    }

    /* Overall color tone */
    .stApp {
        background-color: #fafafa;
    }
</style>
""", unsafe_allow_html=True)

# --- Tabs for Men & Women ---
tabs = st.tabs(["Men", "Women"])

for tab, gender in zip(tabs, ["men", "women"]):
    with tab:
        df = load_board(gender)
        if df.empty or len(df) == 0:
            st.info(
                f"No leaderboard yet for **{gender}**. "
                f"Run `python compute/compute_rtg.py` to generate "
                f"`data/leaderboard_{gender}_{SEASON}.csv`."
            )
            continue

        # Rename & select columns
        df = df.rename(columns={
            "player_name": "Player",
            "team_name": "Team",
            "games": "G",
            "Off": "Offense",
            "Def": "Defense",
            "Overall": "Overall"
        })
        cols = ["Player", "Team", "G", "Offense", "Defense", "Overall"]
        df = df[cols].copy()

        # Format values
        df["G"] = df["G"].astype(int)
        for c in ("Offense", "Defense", "Overall"):
            df[c] = df[c].round(1)

        st.markdown("### 📈 **ACAC Player Impact Leaderboard**")
        st.caption(
            "Player and Team columns are fixed. You can sort by **Games**, **Offense**, **Defense**, or **Overall**."
        )

        # Display Table
        st.dataframe(
            df,
            column_config={
                "Player": st.column_config.TextColumn(disabled=True),
                "Team": st.column_config.TextColumn(disabled=True),
                "G": st.column_config.NumberColumn("Games", format="%d"),
                "Offense": st.column_config.NumberColumn("Offense", format="%.1f"),
                "Defense": st.column_config.NumberColumn("Defense", format="%.1f"),
                "Overall": st.column_config.NumberColumn("Overall", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )