import streamlit as st
import pandas as pd
from datetime import date

SEASON = 2025

st.set_page_config(page_title="ACAC Player Impact Ratings", page_icon="🏀", layout="wide")

# ---------- Header ----------
st.markdown(f"""
<div style="background: linear-gradient(90deg, #002244, #0078D7);
            padding: 1.6rem 2rem; border-radius: 8px; color: white;">
  <h1 style="margin-bottom:0;">🏀 ACAC Player Impact Ratings — {SEASON}</h1>
  <p style="margin-top:0.4rem; font-size:1rem; opacity:0.9;">
     Updated automatically • <b>{date.today():%b %d, %Y}</b>
  </p>
</div>
""", unsafe_allow_html=True)

# ---------- Overview ----------
st.markdown("""
### 📊 What this shows
This leaderboard estimates each player's **overall impact** on their team's performance in the current ACAC season.

**Weights**
- 🎯 **30 %** — Team minute share (on-court value)  
- 📊 **70 %** — Individual box-score impact  

**Ratings**
- 🔴 **Offense:** Scoring & creation impact  
- 🟩 **Defense:** Stops & rebounding impact  
- ⚫ **Overall:** Combined impact (Off + Def)

_Not a WAR metric — this “Impact Index” blends box score and playing time similar to ESPN’s analytics._
---
""")

@st.cache_data
def load_board(gender):
    try:
        return pd.read_csv(f"data/leaderboard_{gender}_{SEASON}.csv")
    except Exception:
        return pd.DataFrame()

# ---------- Styling ----------
st.markdown("""
<style>
thead tr th div {
    justify-content: center !important;
    white-space: nowrap !important;
}
tbody td {
    text-align: center !important;
    white-space: nowrap !important;
}
tr:nth-child(even) { background-color: rgba(200,200,200,0.04); }
tbody td:last-child {
    background: linear-gradient(180deg, #cfcfcf, #bfbfbf);
    font-weight: 700;
}
@media (prefers-color-scheme: dark) {
    tbody td:last-child { background: linear-gradient(180deg, #2a2a2a, #1e1e1e); }
}
.footer {
    margin-top: 3rem; text-align: center; color: gray; font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ---------- Tabs ----------
tabs = st.tabs(["👨 Men", "👩 Women"])

for tab, gender in zip(tabs, ["men", "women"]):
    with tab:
        df = load_board(gender)
        if df.empty:
            st.info(f"No leaderboard yet for **{gender}**.")
            continue

        df = df.rename(columns={
            "player_name": "Player",
            "team_name": "Team",
            "games": "G",
            "Off": "Offense",
            "Def": "Defense",
            "Overall": "Overall"
        })
        df = df[["player_name", "team_name", "games", "Offense", "Defense", "Overall"]]
        df.columns = ["Player", "Team", "G", "Offense", "Defense", "Overall"]

        df.index = range(1, len(df) + 1)
        df.index.name = "#"

        df["G"] = df["G"].astype(int)
        for c in ("Offense", "Defense", "Overall"):
            df[c] = df[c].round(1)

        # Default sort by Overall descending
        df = df.sort_values("Overall", ascending=False)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard")
        st.caption("Player / Team columns fixed • Click **Games**, **Offense**, **Defense**, or **Overall** to sort")

        # One-click sorting table (no edit popup)
        st.data_editor(
            df,
            use_container_width=True,
            hide_index=False,
            disabled=True,
            column_order=["Player", "Team", "G", "Offense", "Defense", "Overall"]
        )

st.markdown("""
<div class="footer"><hr>
© 2025 ACAC Analytics • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)